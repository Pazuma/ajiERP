import assert from "node:assert/strict";
import fs from "node:fs/promises";
import {chromium} from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const browser = await chromium.launch({headless: true, executablePath: "/usr/bin/chromium-headless-shell", args: ["--no-sandbox"]});
const page = await browser.newPage({viewport: {width: 1540, height: 1100}});
const output = new URL("./", import.meta.url).pathname;
const errors = [];
page.on("pageerror", e => { errors.push(e.message); console.error(e.stack); });
try {
    await page.goto((process.env.FRAPPE_BASE_URL || "http://127.0.0.1:8300") + "/login");
    await page.locator("#login_email").fill(process.env.FRAPPE_USER || "Administrator");
    await page.locator("#login_password").fill(process.env.FRAPPE_PASSWORD || "admin");
    await page.locator(".btn-login").click();
    await page.waitForURL(/\/(app|desk)/);
    await page.goto((process.env.FRAPPE_BASE_URL || "http://127.0.0.1:8300") + "/app/product-cost-quotation");
    await page.waitForFunction(() => window.frappe?.boot);
    await page.waitForFunction(() => window.cur_list?.doctype === "Product Cost Quotation" && cur_list.$result?.find(".list-row-container").length);
    const name = await page.evaluate(async () => {
        const {message} = await frappe.call({method: "frappe.client.get_list", args: {doctype: "Product Cost Quotation", filters: {docstatus: 0}, fields: ["name"], limit_page_length: 1}});
        if (!message.length) throw new Error("No existing draft available for read-only UI acceptance");
        frappe.set_route("Form", "Product Cost Quotation", message[0].name);
        return message[0].name;
    });
    await page.waitForFunction(name => window.cur_frm?.doc?.name === name && cur_frm.fields_dict.quote_preview?.$wrapper.find("table").length, name);
    const tabs = page.locator(".form-tabs .nav-link:visible");
    assert.equal(await tabs.count(), 2);
    await page.getByRole("tab", {name: "对客报价", exact: true}).click();
    await page.screenshot({path: output + "产品成本报价单-双页-对客报价.png", fullPage: true});
    await page.getByRole("tab", {name: "成本核算", exact: true}).click();
    await page.screenshot({path: output + "产品成本报价单-双页-成本核算.png", fullPage: true});
    const references = page.locator('.form-section[data-fieldname="references_tab"]');
    if (await references.locator('.section-body').isHidden()) await references.locator('.section-head').click();
    const history = page.locator('[data-fieldname="actual_reference_view"]');
    const warnings = page.locator('[data-fieldname="source_warnings"]');
    await history.scrollIntoViewIfNeeded();
    const left = await history.boundingBox();
    const right = await warnings.boundingBox();
    assert.ok(right.x > left.x + left.width - 5, "来源提示应位于历史数据右侧");
    assert.ok(Math.abs(right.y - left.y) < 30, "来源提示与历史数据应顶部对齐");
    assert.equal(await page.locator('[data-fieldname="snapshot_hash"]').isVisible(), false);
    await page.screenshot({path: output + "产品成本报价单-来源与实际参考.png", fullPage: true});
    const result = await page.evaluate(async () => {
        const api = "client_akivision.api.product_cost_quotation_import.";
        const response = await fetch(`/api/method/${api}export_import_data?name=${encodeURIComponent(cur_frm.doc.name)}`);
        if (!response.ok) throw new Error(await response.text());
        const blob = await response.blob();
        const body = new FormData();
        body.append("file", blob, "pcq-acceptance.xlsx");
        body.append("is_private", "1");
        const uploaded = await fetch("/api/method/upload_file", {method: "POST", body, headers: {"X-Frappe-CSRF-Token": frappe.csrf_token}});
        const file = (await uploaded.json()).message;
        const {message} = await frappe.call({method: api + "preview_import", type: "POST", args: {name: cur_frm.doc.name, file_url: file.file_url, expected_modified: cur_frm.doc.modified}});
        return {errors: message.errors, changes: message.changes.length, bytes: blob.size};
    });
    assert.deepEqual(result.errors, []);
    assert.equal(result.changes, 0);
    assert.deepEqual(errors, []);
    await fs.writeFile(output + "playwright_product_cost_quotation_import_result.json", JSON.stringify({name, tabs: 2, ...result, errors}, null, 2));
    console.log(JSON.stringify({name, tabs: 2, ...result, errors}));
} finally {
    await browser.close();
}
