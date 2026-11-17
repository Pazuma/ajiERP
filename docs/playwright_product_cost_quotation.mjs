import assert from "node:assert/strict";
import fs from "node:fs/promises";
import {chromium} from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const base = process.env.FRAPPE_BASE_URL || "http://127.0.0.1:8300";
const output = new URL("./", import.meta.url).pathname;
const browser = await chromium.launch({headless: true, executablePath: "/usr/bin/chromium-headless-shell", args: ["--no-sandbox"]});
const page = await browser.newPage({viewport: {width: 1540, height: 1050}});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const results = [];
let created;
try {
    await page.goto(`${base}/login`, {waitUntil: "domcontentloaded"});
    await page.locator("#login_email").fill(process.env.FRAPPE_USER || "Administrator");
    await page.locator("#login_password").fill(process.env.FRAPPE_PASSWORD || "admin");
    await page.locator(".btn-login").click();
    await page.waitForURL(/\/(app|desk)/, {timeout: 30000});
    await page.goto(`${base}/app/product-cost-quotation`, {waitUntil: "networkidle"});
    await page.waitForFunction(() => window.frappe?.boot);
    for (const dt of ["Item", "Project", "Work Order"]) {
        const name = await page.evaluate(async (doctype) => {
            const {message} = await frappe.call({method: "frappe.client.get_list", args: {doctype, fields: ["name"], limit_page_length: 1}});
            return message[0]?.name;
        }, dt);
        assert.ok(name, `missing ${dt} fixture`);
        await page.goto(`${base}/app/${dt.toLowerCase().replaceAll(" ", "-")}/${encodeURIComponent(name)}`, {waitUntil: "networkidle"});
        await page.waitForFunction((dt) => window.cur_frm?.doctype === dt && !cur_frm.is_new(), dt);
        await page.getByRole("button", {name: "产品成本报价", exact: true}).waitFor();
        await page.getByRole("button", {name: "产品成本报价", exact: true}).click();
        await page.getByRole("link", {name: "新建成本报价单", exact: true}).click();
        if (dt === "Project") {
            await page.locator('.modal:visible [data-fieldname="provisional_model"] input').fill("PCQ-项目入口验收");
            await page.locator(".modal:visible .modal-title").click();
            await page.locator(".modal:visible .btn-primary").click();
        }
        await page.waitForFunction(() => window.cur_frm?.doctype === "Product Cost Quotation" && cur_frm.is_new());
        const context = await page.evaluate(() => ({source: cur_frm.doc.source_type, scenarios: cur_frm.doc.scenarios.length, item: cur_frm.doc.item_code, project: cur_frm.doc.project, work_order: cur_frm.doc.reference_work_order}));
        assert.equal(context.source, dt);
        assert.equal(context.scenarios, 4);
        if (dt === "Project") assert.equal(context.project, name);
        if (dt === "Work Order") assert.equal(context.work_order, name);
        results.push({name: `${dt}真实页面入口`, status: "passed"});
        // Discard only the unsaved quotation created by this test.
        await page.evaluate(() => {cur_frm.doc.__unsaved = 0;});
    }
    await page.goto(`${base}/app/product-cost-quotation`, {waitUntil: "networkidle"});
    await page.evaluate(() => {frappe.new_doc("Product Cost Quotation");});
    await page.waitForFunction(() => window.cur_frm?.doctype === "Product Cost Quotation" && cur_frm.is_new());
    await page.evaluate(async () => {
        const {message: companies} = await frappe.call({method: "frappe.client.get_list", args: {doctype: "Company", fields: ["name", "default_currency"], limit_page_length: 1}});
        await cur_frm.set_value({company: companies[0].name, currency: companies[0].default_currency, exchange_rate: 1,
            provisional_model: "PCQ-浏览器验收-临时", product_name: "阶梯报价演示产品", tax_rate: 13,
            pricing_method: "Target Margin", target_margin: 40, cost_ratio: 40, minimum_sales_qty: 200});
        cur_frm.clear_table("materials");
        cur_frm.add_child("materials", {description: "演示材料", qty_per_unit: 3, conversion_factor: 1,
            price_basis: "Manual", manual_rate: 10, price_currency: cur_frm.doc.currency, price_exchange_rate: 1,
            tax_basis: "Exclusive", pack_multiple: 1, surplus_policy: "Reusable", loss_method: "None", manual_reason: "验收用价"});
        cur_frm.clear_table("operations");
        cur_frm.add_child("operations", {operation: "组装", charging_basis: "Per Unit", standard_hours: 1, hourly_rate: 80, included_cost_scope: "人工", manual_reason: "验收标准工时"});
        cur_frm.refresh_fields();
        await cur_frm.save();
    });
    created = await page.evaluate(() => cur_frm.doc.name);
    await page.locator(".pcq-matrix").waitFor();
    const state = await page.evaluate(() => ({cost: cur_frm.doc.scenarios[0].full_unit_cost, rows: cur_frm.doc.scenarios.length}));
    assert.equal(state.cost, 110);
    assert.equal(state.rows, 4);
    assert.equal(await page.locator(".pcq-detail").count() > 0, true);
    const css = await page.locator(".pcq-matrix").evaluate((element) => getComputedStyle(element).overflowX);
    assert.equal(css, "auto");
    await page.locator(".pcq-detail").first().click();
    await page.getByRole("dialog").getByText("核算依据与来源详情", {exact: true}).waitFor();
    assert.equal(await page.locator(".modal:visible table tbody tr").count() > 0, true);
    await page.locator(".modal:visible .btn-modal-close").click();
    await page.screenshot({path: `${output}产品成本报价单-实现效果.png`, fullPage: true});
    await page.getByRole("button", {name: "读取来源 / 刷新预览", exact: true}).click();
    await page.getByRole("dialog").getByText("核对来源变更", {exact: true}).waitFor();
    assert.ok((await page.locator(".modal:visible").innerText()).includes("手工行保留"));
    await page.locator('.modal:visible button[data-dismiss="modal"]').first().click();
    results.push({name: "直接新增、服务端核算、刷新预览", status: "passed", cost: state.cost});
    const detail = await page.evaluate(async () => (await frappe.call({method: "client_akivision.api.product_cost_quotation.get_line_detail", args: {name: cur_frm.doc.name, child_row: cur_frm.doc.materials[0].name}})).message);
    assert.equal(detail.calculations.length, 4);
    for (const audience of ["internal", "customer"]) {
        const response = await page.request.get(`${base}/api/method/client_akivision.api.product_cost_quotation.export_cost_quotation?name=${encodeURIComponent(created)}&audience=${audience}`);
        assert.equal(response.status(), 200, await response.text());
        const bytes = await response.body();
        assert.equal(bytes.subarray(0, 2).toString(), "PK");
        await fs.writeFile(`${output}产品成本报价单-${audience}-验收示例.xlsx`, bytes);
    }
    results.push({name: "来源详情、内部与客户实际下载", status: "passed"});
    const blockingErrors = errors.filter((error) => !error.includes("play() failed because the user didn't interact with the document first"));
    assert.deepEqual(blockingErrors, []);
    const result = {passed: true, tested_at: new Date().toISOString(), results, errors: blockingErrors};
    await fs.writeFile(`${output}playwright_product_cost_quotation_result.json`, JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
} catch (error) {
    await page.screenshot({path: `${output}playwright_product_cost_quotation_failure.png`, fullPage: true});
    console.error(JSON.stringify({errors, results}));
    throw error;
} finally {
    if (created) {
        await page.evaluate(async (name) => {
            await frappe.call({method: "frappe.client.delete", args: {doctype: "Product Cost Quotation", name}});
        }, created);
    }
    await browser.close();
}
