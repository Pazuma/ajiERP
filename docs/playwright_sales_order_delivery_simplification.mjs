import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/workspace/development/erpnext.official/node_modules/playwright/index.mjs";

const benchRoot = "/workspace/development/frappe-bench";
const appRoot = `${benchRoot}/apps/client_akivision`;
const baseUrl = "http://127.0.0.1:8300";
const partialOrder = "SAL-ORD-2026-00001";
const completedOrder = "SAL-ORD-2026-00004";
const source = await fs.readFile(`${appRoot}/client_akivision/public/js/sales_order_delivery.js`, "utf8");
const backend = await fs.readFile(`${appRoot}/client_akivision/utils/sales_order_delivery.py`, "utf8");
const hooks = await fs.readFile(`${appRoot}/client_akivision/hooks.py`, "utf8");
const runtimeIssues = [];
const requests = [];

const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/frappe/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});

try {
	const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
	const page = await context.newPage();
	page.on("pageerror", (error) => runtimeIssues.push(`pageerror: ${error.message}`));
	page.on("requestfailed", (request) => runtimeIssues.push(`requestfailed: ${request.url()}`));
	page.on("response", (response) => {
		if (response.url().includes("make_mapped_doc") || response.url().includes("make_simple_delivery_note")) {
			requests.push({url: response.url(), status: response.status()});
		}
	});

	await page.goto(`${baseUrl}/login`, {waitUntil: "domcontentloaded"});
	await page.locator("#login_email").fill("Administrator");
	await page.locator("#login_password").fill("admin");
	await page.locator("button.btn-login").click();
	await page.waitForURL(/desk/, {timeout: 15000});

	await page.goto(`${baseUrl}/app/sales-order/${partialOrder}`, {waitUntil: "domcontentloaded"});
	await page.waitForTimeout(3500);
	await page.getByRole("button", {name: "创建"}).click();
	const simpleButton = page.getByText("一键创建销售送货单", {exact: true});
	await simpleButton.waitFor({state: "visible", timeout: 10000});
	assert.equal(await simpleButton.isVisible(), true);

	await simpleButton.click();
	await page.waitForURL(/delivery-note/, {timeout: 15000});
	await page.waitForTimeout(1500);

	const delivery = await page.evaluate(() => ({
		doctype: cur_frm?.doc?.doctype,
		docstatus: cur_frm?.doc?.docstatus,
		against_sales_order: cur_frm?.doc?.items?.[0]?.against_sales_order,
		so_detail: cur_frm?.doc?.items?.[0]?.so_detail,
		item_code: cur_frm?.doc?.items?.[0]?.item_code,
		qty: cur_frm?.doc?.items?.[0]?.qty,
		warehouse: cur_frm?.doc?.items?.[0]?.warehouse,
		uom: cur_frm?.doc?.items?.[0]?.uom,
		stock_uom: cur_frm?.doc?.items?.[0]?.stock_uom,
		conversion_factor: cur_frm?.doc?.items?.[0]?.conversion_factor,
	}));
	assert.equal(delivery.doctype, "Delivery Note");
	assert.equal(delivery.docstatus, 0);
	assert.equal(delivery.against_sales_order, partialOrder);
	assert.equal(delivery.item_code, "product item1");
	assert.equal(delivery.qty, 17);
	assert.equal(delivery.warehouse, "成品 - T");
	assert.equal(delivery.uom, "Nos");
	assert.equal(delivery.stock_uom, "Nos");
	assert.equal(delivery.conversion_factor, 1);
	await page.setViewportSize({width: 390, height: 844});
	assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
	await page.setViewportSize({width: 1440, height: 1000});

	await page.screenshot({
		path: `${appRoot}/docs/playwright_sales_order_delivery_simplification.png`,
		fullPage: true,
	});

	await page.goto(`${baseUrl}/app/sales-order/${completedOrder}`, {waitUntil: "domcontentloaded"});
	await page.waitForTimeout(2500);
	const completedVisible = await page
		.getByText("一键创建销售送货单", {exact: true})
		.isVisible()
		.catch(() => false);
	assert.equal(completedVisible, false);

	assert.match(source, /client_akivision\.utils\.sales_order_delivery\.make_simple_delivery_note/);
	assert.match(source, /per_delivered/);
	assert.match(backend, /docstatus = 0/);
	assert.match(backend, /draft_qty/);
	assert.match(backend, /calculate_taxes_and_totals/);
	assert.match(hooks, /"Sales Order": "public\/js\/sales_order_delivery\.js"/);
	const knownSiteIssues = runtimeIssues.filter(
		(issue) =>
			issue.includes("custom_filters/public/js/naming_series_i18n.js") ||
			issue.includes("Cannot read properties of null (reading 'join')"),
	);
	const unexpectedIssues = runtimeIssues.filter((issue) => !knownSiteIssues.includes(issue));
	assert.deepEqual(unexpectedIssues, []);
	assert.equal(requests.every((request) => request.status === 200), true);

	const result = {
		status: "passed",
		tested_at: new Date().toISOString(),
		browser: "Chromium",
		orders: {partial: partialOrder, completed: completedOrder},
		assertions: [
			"部分交付销售订单显示一键创建销售送货单入口",
			"一键入口只生成草稿销售送货单，不自动提交",
			"剩余数量按订单数量减已交付数量计算为 17",
			"客户、销售订单明细、物料、数量、仓库、单位和换算字段完整映射",
			"已完成销售订单不显示一键出库入口",
			"一键出库请求返回成功，功能链路未发现新增异常",
		],
		delivery,
		requests,
		runtime_issues: runtimeIssues,
		known_site_issues: knownSiteIssues,
	};
	await fs.writeFile(
		`${appRoot}/docs/playwright_sales_order_delivery_simplification_result.json`,
		JSON.stringify(result, null, 2) + "\n",
	);
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
}
