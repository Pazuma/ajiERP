import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/client_akivision";
const jqueryPath = "/home/cst/frappe_docker/development/frappe-bench/apps/frappe/frappe/public/js/lib/jquery/jquery.min.js";
const importJs = await fs.readFile(path.join(appRoot, "public/js/data_import.js"), "utf8");
const importCss = await fs.readFile(path.join(appRoot, "public/css/data_import.css"), "utf8");
const jqueryJs = await fs.readFile(jqueryPath, "utf8");

const tables = [
	{sheet_id: "product_list", table_label: "产品清单", doctype: "Item", importable: true},
	{sheet_id: "sales_order", table_label: "销售订单", doctype: "Sales Order", importable: true},
	{sheet_id: "live_stock", table_label: "实时库存", doctype: null, importable: false, disabled_reason: "库存实时计算结果，只读，不允许导入"},
];

const fields = {
	product_list: [{key: "Item", label: "物料", doctype: "Item", fields: [
		{fieldname: "item_code", label: "物料编码", writable: true, default_selected: true, reqd: true},
		{fieldname: "item_name", label: "物料名称", writable: true, default_selected: true},
		{fieldname: "description", label: "说明", writable: true, default_selected: true},
	]}],
	sales_order: [
		{key: "Sales Order", label: "销售订单", doctype: "Sales Order", fields: [
			{fieldname: "customer", label: "客户", writable: true, default_selected: true, reqd: true},
			{fieldname: "transaction_date", label: "订单日期", writable: true, default_selected: true, reqd: true},
		]},
		{key: "items", label: "订单明细", doctype: "Sales Order Item", fields: [
			{fieldname: "item_code", label: "物料编码", writable: true, default_selected: true, reqd: true},
			{fieldname: "qty", label: "数量", writable: true, default_selected: true, reqd: true},
		]},
	],
};

const presentations = {
	product_list: {
		sheet_id: "product_list", sheet: "产品清单", doctype: "Item", importable: true,
		list_fields: ["物料编码", "物料名称", "物料类别"],
		detail_sections: [{label: "基础资料", fields: ["说明", "版本", "工程图纸"]}],
		child_tables: [], related_records: ["BOM与工程图纸", "库存流水"], computed_fields: ["当前库存", "在途量"],
	},
	sales_order: {
		sheet_id: "sales_order", sheet: "销售订单", doctype: "Sales Order", importable: true,
		list_fields: ["系统单号", "客户", "订单日期"],
		detail_sections: [{label: "订单头信息", fields: ["收款条件", "合同附件"]}],
		child_tables: [{table_field: "items", label: "订单明细", fields: ["物料编码", "数量", "单价"]}],
		related_records: ["送货单", "销售发票", "收款单"], computed_fields: ["订单金额", "未送货量", "收款状态"],
	},
};

const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
body { font-family: sans-serif; margin: 24px; }
.client-import-selector { width: 900px; }
${importCss}
</style></head><body><div id="form-root"><div id="reference-field">reference</div></div>
<script>${jqueryJs}</script>
<script>
window.__ = (value, args) => {
	if (!args) return value;
	return value.replace(/\\{(\\d+)\\}/g, (_, index) => args[index] ?? "");
};
window.frappe = {
	ui: {form: {on: () => {}}},
	utils: {escape_html: (value) => String(value).replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","'":"&#39;"}[char]))},
	call: async (method, args = {}) => {
		if (method.endsWith("get_import_modules")) return {message: [{module_key: "Stock", module_label: "库存", importable_count: 2}]};
		if (method.endsWith("get_import_tables")) return {message: ${JSON.stringify(tables)}};
		if (method.endsWith("get_import_fields")) return {message: window.__fields[args.sheet_id]};
		if (method.endsWith("get_import_presentation")) return {message: window.__presentations[args.sheet_id]};
		throw new Error("Unexpected frappe.call: " + method);
	},
};
window.__fields = ${JSON.stringify(fields)};
window.__presentations = ${JSON.stringify(presentations)};
window.__frm = {is_new: () => true, $wrapper: $("#form-root"), get_field: () => ({$wrapper: $("#reference-field")})};
</script>
<script>${importJs}</script>
<script>window.__ready = window.client_akivision.render_import_selector(window.__frm);</script>
</body></html>`;

const server = http.createServer((request, response) => {
	if (request.url === "/") {
		response.writeHead(200, {"content-type": "text/html; charset=utf-8"});
		response.end(html);
		return;
	}
	response.writeHead(404);
	response.end("not found");
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({viewport: {width: 1440, height: 1000}, deviceScaleFactor: 1});
const results = [];

try {
	await page.goto(`http://127.0.0.1:${port}/`, {waitUntil: "load"});
	await page.evaluate(() => window.__ready);
	await page.locator(".client-import-presentation").waitFor();
	const liveStockOption = page.locator('[data-role="sheet"] option[value="live_stock"]');
	assert.equal(await liveStockOption.isDisabled(), true);
	assert.match(await liveStockOption.innerText(), /实时库存/);
	results.push({name: "只读报表不可导入", status: "passed", details: "实时库存选项被禁用"});
	const initialText = await page.locator(".client-import-presentation").innerText();
	assert.match(initialText, /导入后查看位置/);
	assert.match(initialText, /列表: 物料编码、物料名称、物料类别/);
	assert.match(initialText, /详情: 基础资料：说明、版本、工程图纸/);
	assert.match(initialText, /系统计算（只读）: 当前库存、在途量/);
	results.push({name: "产品清单展示去向", status: "passed", details: "列表、详情和系统计算字段均显示"});

	await page.selectOption('[data-role="sheet"]', "sales_order");
	await page.locator(".client-import-presentation").waitFor();
	await page.waitForFunction(() => document.querySelector(".client-import-presentation")?.innerText.includes("订单金额"));
	const orderText = await page.locator(".client-import-presentation").innerText();
	assert.match(orderText, /列表: 系统单号、客户、订单日期/);
	assert.match(orderText, /子表: 订单明细：物料编码、数量、单价/);
	assert.match(orderText, /关联记录: 送货单、销售发票、收款单/);
	assert.match(orderText, /系统计算（只读）: 订单金额、未送货量、收款状态/);
	assert.equal(await page.locator('input[data-fieldname="订单金额"]').count(), 0);
	assert.equal(await page.locator('input[data-fieldname="qty"]').count(), 1);
	results.push({name: "销售订单计算字段与明细", status: "passed", details: "计算字段只读说明显示，订单金额未出现在可写字段选择器，明细数量可选"});

	await page.screenshot({path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_excel_import_sales_order.png", fullPage: true});
	await fs.writeFile(
		"/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_excel_import_result.json",
		JSON.stringify({tested_at: new Date().toISOString(), browser: "Chromium 151", base_url: `http://127.0.0.1:${port}/`, results}, null, 2) + "\n",
	);
	console.log(JSON.stringify({status: "passed", results}, null, 2));
} finally {
	await browser.close();
	await new Promise((resolve) => server.close(resolve));
}
