import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const root = "/home/cst/frappe_docker";
const source = await fs.readFile(`${root}/development/frappe-bench/apps/mes_integration/mes_integration/public/js/purchase_order.js`, "utf8");
const css = await fs.readFile(`${root}/development/frappe-bench/apps/mes_integration/mes_integration/public/css/purchase_order.css`, "utf8");
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const results = [];

try {
	const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
	await page.setContent(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
		body { font-family: Arial, sans-serif; margin: 24px; color: #36414c; }
		.table { border-collapse: collapse; width: 100%; } .table th, .table td { border: 1px solid #d1d8dd; padding: 7px; white-space: nowrap; }
		.text-right { text-align: right; } .text-center { text-align: center; } .text-muted { color: #6c7680; }
		${css}
	</style></head><body><main id="item-wrapper"></main></body></html>`);

	await page.evaluate((formSource) => {
		window.__ = (value) => value;
		window.flt = (value) => Number(value || 0);
		window.format_number = (value) => String(Number(value || 0));
		window.format_currency = (value, currency) => `${currency} ${Number(value || 0).toFixed(2)}`;
		window.__handlers = {};
		window.jQuery = (selector) => {
			const nodes = typeof selector === "string" ? [...document.querySelectorAll(selector)] : (Array.isArray(selector) ? selector : [selector]);
			const api = {
				get length() { return nodes.length; },
				find: (value) => window.jQuery(nodes.flatMap((node) => [...node.querySelectorAll(value)])),
				append: (html) => nodes.forEach((node) => node.insertAdjacentHTML("beforeend", html)),
				remove: () => nodes.forEach((node) => node.remove()),
				empty: () => { nodes.forEach((node) => { node.innerHTML = ""; }); return api; },
				hide: () => { nodes.forEach((node) => { node.style.display = "none"; }); return api; },
				show: () => { nodes.forEach((node) => { node.style.display = ""; }); return api; },
				html: (html) => { nodes.forEach((node) => { node.innerHTML = html; }); return api; },
				on: (event, handler) => { nodes.forEach((node) => node.addEventListener(event, handler)); return api; },
				prop: (name, value) => { nodes.forEach((node) => { node[name] = value; }); return api; },
				attr: (values) => { nodes.forEach((node) => Object.entries(values).forEach(([name, value]) => node.setAttribute(name, value))); return api; },
				toggleClass: (name, enabled) => { nodes.forEach((node) => node.classList.toggle(name, enabled)); return api; },
				hasClass: (name) => nodes.some((node) => node.classList.contains(name)),
			};
			return api;
		};
		window.frappe = {
			ui: { form: { on(doctype, handlers) { window.__handlers[doctype] = handlers; } } },
			utils: { escape_html: (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]) },
			call({ method, callback }) {
				if (method.includes("preview_aggregate_item_pricing")) {
					callback({ message: { row_updates: window.__doc.items.map((row) => ({ name: row.name, item_code: row.item_code, total_stock_qty: 300, price_list_rate: 0.08, discount_percentage: 0, discount_amount: 0, rate: 0.08, pricing_rules: '["BUY-SCREW-300"]' })), warnings: [] } });
					return;
				}
				if (method.includes("get_actual_arrival_summary")) {
					callback({ message: { arrivals: [{ purchase_receipt: "PRE-0001", posting_date: "2026-08-28", purchase_order_item: "ROW-1", item_code: "SCREW", item_name: "螺丝", qty: 120, uom: "个", rate: 0.08, amount: 9.6, warehouse: "原料仓" }], summary: [{ purchase_order_item: "ROW-1", item_code: "SCREW", received_qty: 120, remaining_qty: 180, uom: "个" }] } });
					return;
				}
				if (method.includes("make_purchase_receipt")) callback({ message: { doctype: "Purchase Receipt", name: "new-purchase-receipt" } });
			},
			model: { sync: (doc) => [doc] },
			set_route: (...route) => { window.__route = route; },
		};
		window.__doc = { name: "PO-0001", supplier: "供应商A", currency: "CNY", docstatus: 1, items: [
			{ name: "ROW-1", item_code: "SCREW", qty: 100, stock_qty: 100, uom: "个", warehouse: "原料仓", rate: 0.1 },
			{ name: "ROW-2", item_code: "SCREW", qty: 200, stock_qty: 200, uom: "个", warehouse: "成品仓", rate: 0.1 },
		] };
		window.__frm = { doc: window.__doc, fields_dict: { items: { $wrapper: window.jQuery("#item-wrapper") } }, is_new: () => false, refresh_field: () => {}, cscript: { calculate_taxes_and_totals: () => { window.__totalsCalculated = true; } }, add_custom_button(label, action) { const button = document.createElement("button"); button.textContent = label; button.onclick = action; document.body.append(button); } };
		(0, eval)(formSource);
	}, source);

	await page.evaluate(() => window.__handlers["Purchase Order"].refresh(window.__frm));
	for (const label of ["采购收货单", "收货日期", "物料编码", "物料名称", "实际到货数量", "单位", "单价", "金额", "收料仓", "累计到货", "剩余未到货"]) assert.equal(await page.getByText(label, { exact: true }).count(), 1, `missing ${label}`);
	assert.equal(await page.locator(".mes-po-arrivals tbody tr").count(), 1);
	results.push({ name: "实际到货字段", status: "passed", details: "展示收货单、日期、物料、数量、单位、单价、金额、收料仓、累计和剩余数量" });

	await page.locator(".mes-po-collapse-toggle").click();
	assert.equal(await page.locator(".mes-po-arrivals-content").isVisible(), false);
	await page.locator(".mes-po-collapse-toggle").click();
	assert.equal(await page.locator(".mes-po-arrivals-content").isVisible(), true);
	results.push({ name: "实际到货收纳", status: "passed", details: "区域可展开/收纳，收纳后隐藏汇总、表格和操作条" });

	await page.evaluate(() => window.__handlers["Purchase Order Item"].qty(window.__frm));
	await page.waitForTimeout(350);
	const pricing = await page.evaluate(() => ({ rates: window.__doc.items.map((row) => row.rate), totalsCalculated: window.__totalsCalculated }));
	assert.deepEqual(pricing.rates, [0.08, 0.08]);
	assert.equal(pricing.totalsCalculated, true);
	assert.match(await page.locator(".mes-po-aggregate-price-note").innerText(), /合计数量 300/);
	assert.match(await page.locator(".mes-po-aggregate-price-note").innerText(), /CNY 0\.10 -> CNY 0\.08/);
	results.push({ name: "同物料跨仓阶梯价", status: "passed", details: "两行不同仓库按合计 300 取价，均回写为 0.08，并展示单价调整提示" });

	await page.getByRole("button", { name: "添加行" }).click();
	assert.deepEqual(await page.evaluate(() => window.__route), ["Form", "Purchase Receipt", "new-purchase-receipt"]);
	results.push({ name: "标准收货入口", status: "passed", details: "实际到货表的添加行使用 Purchase Order 标准采购收货映射" });

	await page.setViewportSize({ width: 390, height: 844 });
	const mobile = await page.locator(".mes-po-arrivals-table-wrap").evaluate((node) => ({ overflowX: getComputedStyle(node).overflowX, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth }));
	assert.equal(mobile.overflowX, "auto");
	assert.ok(mobile.scrollWidth > mobile.clientWidth);
	results.push({ name: "移动端表格", status: "passed", details: "宽表在容器内横向滚动，汇总区换行显示" });

	await page.screenshot({ path: `${root}/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing.png`, fullPage: true });
	await fs.writeFile(`${root}/development/frappe-bench/apps/client_akivision/docs/playwright_purchase_order_aggregate_pricing_result.json`, JSON.stringify({ tested_at: new Date().toISOString(), browser: "Chromium", mode: "Frappe form and API mock", results }, null, 2) + "\n");
	console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
	await browser.close();
}
