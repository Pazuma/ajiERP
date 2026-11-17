import { chromium } from "../development/erpnext.official/node_modules/playwright/index.mjs";
import { mkdir, writeFile } from "node:fs/promises";

const baseUrl = process.env.SALES_PRODUCT_TEST_URL || "http://127.0.0.1:8300";
const output = new URL("./sales-product-test-evidence/", import.meta.url).pathname;
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const errors = [];
page.on("pageerror", error => errors.push(error.message));
try {
	await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
	await page.locator("#login_email").fill(process.env.SALES_PRODUCT_TEST_USER || "Administrator");
	await page.locator("#login_password").fill(process.env.SALES_PRODUCT_TEST_PASSWORD || "admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/\/app|\/desk/, { timeout: 30000 });
	await page.goto(`${baseUrl}/app/sales-products`, { waitUntil: "domcontentloaded" });
	await page.waitForFunction(() => window.cur_list?.doctype === "Item" && window.cur_list?.page?.title === "产品表", null, { timeout: 30000 });
	const list = await page.evaluate(() => ({
		url: location.pathname,
		doctype: cur_list.doctype,
		title: cur_list.page.title,
		filters: cur_list.filter_area.get(),
		rows: cur_list.data.map(row => row.name),
	}));
	if (!list.filters.some(filter => filter[1] === "is_sales_item" && Number(filter[3]) === 1)) throw new Error("Missing sales filter");
	if (!list.filters.some(filter => filter[1] === "disabled" && Number(filter[3]) === 0)) throw new Error("Missing enabled filter");
	await page.screenshot({ path: `${output}product-list-desktop.png`, fullPage: true });
	await page.evaluate(() => {
		for (const button of document.querySelectorAll(".modal.show .close, .modal.show [data-dismiss='modal'], .modal.show .modal-header .btn")) button.click();
		for (const dialog of document.querySelectorAll(".modal.show")) window.bootstrap?.Modal?.getInstance(dialog)?.hide();
	});
	await page.evaluate(() => $(".page-container:visible .primary-action")[0]?.click());
	await page.waitForFunction(() => window.cur_dialog?.title === "新增产品");
	const fields = await page.evaluate(() => Object.keys(cur_dialog.fields_dict));
	for (const field of ["item_code", "item_name", "brand", "image", "description", "price_list", "currency", "price"]) {
		if (!fields.includes(field)) throw new Error(`Missing create field: ${field}`);
	}
	await page.screenshot({ path: `${output}product-create-desktop.png`, fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: `${output}product-create-mobile.png`, fullPage: true });
	await page.evaluate(() => cur_dialog.hide());
	await page.screenshot({ path: `${output}product-list-mobile.png`, fullPage: true });
	await page.setViewportSize({ width: 1440, height: 960 });
	await page.evaluate(() => frappe.new_doc("Sales Order"));
	await page.waitForFunction(() => window.cur_frm?.doctype === "Sales Order", null, { timeout: 30000 });
	await page.waitForFunction(() => document.body.innerText.includes("查看产品库存"), null, { timeout: 30000 });
	await page.screenshot({ path: `${output}sales-order-stock-desktop.png`, fullPage: true });
	await writeFile(`${output}browser-result.json`, JSON.stringify({ list, fields, errors }, null, 2));
	console.log(JSON.stringify({ list, fields, errors }, null, 2));
	if (errors.length) throw new Error(errors.join("; "));
} finally {
	await browser.close();
}
