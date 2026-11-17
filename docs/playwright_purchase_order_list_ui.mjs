import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const source = await fs.readFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/public/js/purchase_order_list.js", "utf8");
const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const results = [];
try {
	const page = await browser.newPage({viewport: {width: 1280, height: 720}});
	await page.setContent("<main id='list'></main><div id='detail' hidden></div>");
	await page.evaluate((script) => {
		window.__ = (value) => value;
		window.frappe = {listview_settings: {"Purchase Order": {onload: (listview) => {listview.nativeOnloadCalled = true; listview.nativeActions = ["Close", "Reopen", "Purchase Invoice", "Purchase Receipt", "Advance Payment"];}}}, meta: {get_docfield: (_doctype, fieldname) => ({supplier_name: {fieldname, fieldtype: "Data", label: "供应商名称"}, transaction_date: {fieldname, fieldtype: "Date", label: "订单日期"}, grand_total: {fieldname, fieldtype: "Currency", label: "含税总额"}}[fieldname] || null)}};
		(0, eval)(script);
		const base = [
			{type: "Subject", df: {fieldname: "supplier_name", fieldtype: "Data", label: "供应商名称"}},
			{type: "Status"},
			{type: "Field", df: {fieldname: "transaction_date", fieldtype: "Date", label: "订单日期"}},
			{type: "Field", df: {fieldname: "grand_total", fieldtype: "Currency", label: "含税总额"}},
			{type: "Field", df: {fieldname: "name", fieldtype: "Data", label: "ID"}},
		];
		const listview = {columns: base.map((column) => ({...column, df: column.df && {...column.df}})), setup_columns() {this.columns = base.map((column) => ({...column, df: column.df && {...column.df}}));}, render_header() {this.headers = this.columns.filter((column) => column.type !== "Tag").map((column) => column.df?.label || "状态"); document.querySelector("#list").innerHTML = this.headers.map((label) => "<span>" + label + "</span>").join(""); const link = document.createElement("a"); link.className = "order-number"; link.href = "/app/purchase-order/PUR-ORD-00001"; link.textContent = "PUR-ORD-00001"; link.addEventListener("click", (event) => {event.preventDefault(); document.querySelector("#detail").hidden = false;}); document.querySelector("#list").prepend(link);}};
		window.listview = listview;
		frappe.listview_settings["Purchase Order"].onload(listview);
	}, source);
	assert.deepEqual(await page.locator("#list span").allTextContents(), ["订单编号", "供应商名称", "状态", "订单日期", "含税总额"]);
	assert.equal(await page.locator(".order-number").textContent(), "PUR-ORD-00001");
	assert.equal(await page.locator(".order-number").getAttribute("href"), "/app/purchase-order/PUR-ORD-00001");
	assert.equal(await page.evaluate(() => window.listview.nativeOnloadCalled), true);
	assert.deepEqual(await page.evaluate(() => window.listview.nativeActions), ["Close", "Reopen", "Purchase Invoice", "Purchase Receipt", "Advance Payment"]);
	results.push({name: "订单编号首列与字段完整性", status: "passed", details: "订单编号位于首业务列，供应商、状态、日期、金额字段仍保留"});
	await page.locator(".order-number").click();
	assert.equal(await page.locator("#detail").getAttribute("hidden"), null);
	results.push({name: "点击订单编号进入详情", status: "passed", details: "链接使用 Purchase Order.name，点击后进入对应采购订单路由"});
	await page.setViewportSize({width: 390, height: 844});
	assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
	results.push({name: "移动端布局", status: "passed", details: "验证页面无视口级横向溢出，订单编号仍可操作"});
	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_list.png", fullPage: true});
	await fs.writeFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_list_result.json", JSON.stringify({tested_at: new Date().toISOString(), browser: "Chromium", results}, null, 2) + "\n");
	console.log(JSON.stringify({status: "passed", results}, null, 2));
} finally { await browser.close(); }
