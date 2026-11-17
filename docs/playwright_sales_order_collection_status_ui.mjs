import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision/client_akivision";
const docsRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs";
const jqueryJs = await fs.readFile("/home/cst/frappe_docker/development/frappe-bench/apps/frappe/frappe/public/js/lib/jquery/jquery.min.js", "utf8");
const reportJs = await fs.readFile(path.join(appRoot, "report/sales_order_list/sales_order_list.js"), "utf8");
const reportPy = await fs.readFile(path.join(appRoot, "report/sales_order_list/sales_order_list.py"), "utf8");

const sampleRows = [
	{
		name: "SO-UNPAID",
		customer_name: "客户未付款",
		completion_status: "已交货",
		invoice_status: "已开票",
		collection_status: "未付款",
		final_status: "待收款",
		completion_flag: "未完成",
		indent: 0,
	},
	{
		name: "SO-PAID",
		customer_name: "客户已付款",
		completion_status: "已交货",
		invoice_status: "已开票",
		collection_status: "已付款",
		final_status: "已完成",
		completion_flag: "已完成",
		indent: 0,
	},
];

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { margin: 0; font-family: Arial, sans-serif; color: #243143; background: #f8fafc; }
.report-page { max-width: 1320px; margin: 0 auto; padding: 20px; }
.report-title { margin: 0 0 12px; font-size: 20px; }
.filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.filter-bar select { min-width: 220px; min-height: 32px; }
.table-wrap { overflow-x: auto; background: #fff; border: 1px solid #e2e8f0; }
table { border-collapse: collapse; min-width: 960px; width: 100%; }
th, td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; text-align: left; white-space: nowrap; }
th { background: #f1f5f9; font-weight: 600; }
.indicator-pill { display: inline-flex; align-items: center; min-height: 22px; padding: 0 9px; border-radius: 999px; font-size: 12px; }
.indicator-pill.green { color: #146c43; background: #d1e7dd; }
.indicator-pill.orange { color: #984c0c; background: #ffe5d0; }
.indicator-pill.red { color: #b02a37; background: #f8d7da; }
</style></head><body><main class="report-page">
<h1 class="report-title">销售订单状态</h1><div class="filter-bar"><label>订单状态 <select id="status-filter"></select></label></div>
<div class="table-wrap"><table><thead><tr><th>销售订单</th><th>客户</th><th>交付状态</th><th>开票状态</th><th>收款状态</th><th>最终状态</th></tr></thead><tbody id="rows"></tbody></table></div>
</main><script>${jqueryJs}</script><script>
window.__ = (value) => value;
window.frappe = {query_reports: {}, defaults: {get_user_default: () => "示例公司"}, utils: {escape_html: (value) => String(value ?? "").replace(/[&<>\"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}};
</script><script>${reportJs}</script></body></html>`;

const browser = await chromium.launch({headless: true, executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args: ["--no-sandbox"]});
const results = [];
const record = (name, details) => results.push({name, status: "passed", details});

try {
	const page = await browser.newPage({viewport: {width: 1440, height: 900}, deviceScaleFactor: 1});
	await page.setContent(html, {waitUntil: "load"});
	await page.addScriptTag({content: jqueryJs});
	await page.evaluate(() => {
		window.__ = (value) => value;
		window.frappe = {query_reports: {}, defaults: {get_user_default: () => "示例公司"}, datetime: {year_start: () => "2026-01-01", year_end: () => "2026-12-31"}, utils: {escape_html: (value) => String(value ?? "").replace(/[&<>\"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}};
	});
	await page.evaluate((source) => window.eval(source), reportJs);
	const report = await page.evaluate(() => window.frappe?.query_reports?.["Sales Order List"]);
	assert.ok(report, "Sales Order List report config is missing");
	const statusFilter = report.filters.find((filter) => filter.fieldname === "status");
	const statuses = statusFilter.options.split("\n").filter(Boolean);
	for (const status of ["已交货", "待开票", "待收款", "部分收款", "已付款", "已完成"]) assert.ok(statuses.includes(status), `missing status option: ${status}`);
	record("订单状态筛选", "交付、开票、收款和最终完成状态均可筛选");

	for (const fieldname of ["completion_status", "invoice_status", "collection_status", "final_status", "received_amount", "outstanding_amount", "invoice_no"]) {
		assert.match(reportPy, new RegExp(`\\"fieldname\\": \\"${fieldname}\\"`), `missing report column: ${fieldname}`);
	}
	record("报表字段完整", "交付、开票、收款、最终状态、收款金额、未结金额和发票号字段均存在");

	await page.evaluate(({rows}) => {
		const config = window.frappe.query_reports["Sales Order List"];
		const statusFilter = document.querySelector("#status-filter");
		for (const option of config.filters.find((filter) => filter.fieldname === "status").options.split("\n")) {
			const element = document.createElement("option"); element.value = option; element.textContent = option || "全部"; statusFilter.appendChild(element);
		}
		const column = (fieldname) => ({fieldname});
		const tbody = document.querySelector("#rows");
		for (const row of rows) {
			const tr = document.createElement("tr");
			for (const fieldname of ["name", "customer_name", "completion_status", "invoice_status", "collection_status", "final_status"]) {
				const td = document.createElement("td");
				const value = row[fieldname];
				td.innerHTML = config.formatter(value, null, column(fieldname), row, (input) => String(input ?? ""));
				tr.appendChild(td);
			}
			tbody.appendChild(tr);
		}
	}, {rows: sampleRows});

	const bodyText = await page.locator("body").innerText();
	assert.match(bodyText, /客户未付款/);
	assert.match(bodyText, /待收款/);
	assert.match(bodyText, /客户已付款/);
	assert.match(bodyText, /已完成/);
	assert.equal(await page.locator(".indicator-pill.green").count() > 0, true);
	assert.equal(await page.locator(".indicator-pill.orange").count() > 0, true);
	record("未付款与已付款展示", "未付款订单显示待收款，已付款订单显示已完成，并使用不同颜色标识");

	await page.screenshot({path: path.join(docsRoot, "playwright_sales_order_collection_status_desktop.png"), fullPage: true});
	await page.setViewportSize({width: 390, height: 844});
	const mobile = await page.evaluate(() => ({clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, tableWraps: document.querySelectorAll(".table-wrap").length}));
	assert.equal(mobile.tableWraps, 1);
	assert.ok(mobile.scrollWidth <= mobile.clientWidth + 1, `unexpected page overflow: ${JSON.stringify(mobile)}`);
	record("移动端布局", "页面容器无横向溢出，宽表在独立区域内滚动");
	await page.screenshot({path: path.join(docsRoot, "playwright_sales_order_collection_status_mobile.png"), fullPage: true});

	const result = {status: "passed", tested_at: new Date().toISOString(), browser: "Chromium", results, limitations: ["使用模拟报表行验证前端字段、状态和布局；未替代真实 Frappe 登录、权限和 MariaDB 数据关联验证", "真实环境需用一笔未付款发票和一笔已付款发票复核后端 SQL 结果"]};
	await fs.writeFile(path.join(docsRoot, "playwright_sales_order_collection_status_result.json"), JSON.stringify(result, null, 2) + "\n");
	console.log(JSON.stringify(result, null, 2));
} finally {
	await browser.close();
}
