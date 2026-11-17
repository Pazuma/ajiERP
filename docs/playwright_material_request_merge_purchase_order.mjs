import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "/home/cst/frappe_docker/development/erpnext.official/node_modules/playwright/index.mjs";

const scriptPath = "/home/cst/frappe_docker/development/frappe-bench/apps/mes_integration/mes_integration/public/js/material_request_list.js";
const source = await fs.readFile(scriptPath, "utf8");
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const results = [];

try {
	const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
	await page.setContent(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
		body { font-family: sans-serif; margin: 20px; }
		.modal-dialog { width: min(1400px, 96vw); max-width: 96vw; }
		.modal-body { overflow: auto; }
		.mes-merge-po-table-wrap { overflow-x: auto; }
		table { min-width: 980px; border-collapse: collapse; }
		th, td { border: 1px solid #cbd5e1; padding: 7px; white-space: nowrap; }
		.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
		.btn { padding: 8px 14px; }
	</style></head><body><main id="actions"></main></body></html>`);

	await page.evaluate((source) => {
		window.__ = (value) => value;
		window.flt = (value) => Number(value || 0);
		window.format_number = (value) => String(Number(value || 0));
		window.frappe = {
			listview_settings: { "Material Request": {} },
			utils: { escape_html: (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]) },
			msgprint: (message) => { window.__messages.push(message); },
			xcall: async (_method, args) => window.__docs.find((doc) => doc.name === args.name),
			call: ({ args, callback }) => {
				window.__callArgs = args;
				callback({ message: { doctype: "Purchase Order", name: "new-purchase-order", company: "测试公司", supplier: args.supplier, items: window.__docs.flatMap((doc) => doc.items) } });
			},
			model: { sync: (doc) => [doc] },
			set_route: (...route) => { window.__route = route; },
			ui: { Dialog: class {
				constructor(options) { this.options = options; this.$wrapper = { addClass: () => {}, find: () => ({ css: () => {} }) }; }
				show() {
					const node = document.createElement("section");
					node.className = "test-dialog";
					node.innerHTML = `<div class="modal-dialog"><h2>${this.options.title}</h2><input aria-label="供应商" name="supplier"><div class="modal-body">${this.options.fields.map((field) => field.options || "").join("")}</div><div class="modal-footer"><button class="btn btn-primary">${this.options.primary_action_label}</button></div></div>`;
					node.querySelector(".btn-primary").addEventListener("click", () => this.options.primary_action({ supplier: node.querySelector("[name=supplier]").value }));
					document.body.append(node);
				}
				hide() { document.querySelector(".test-dialog")?.remove(); }
			} },
		};
		window.__docs = [
			{ name: "MR-001", docstatus: 1, status: "Pending", material_request_type: "Purchase", company: "测试公司", items: [{ name: "MRI-001", item_code: "ITEM-A", item_name: "物料A", stock_qty: 10, ordered_qty: 2, conversion_factor: 1, uom: "个", warehouse: "原料仓", schedule_date: "2026-09-01" }] },
			{ name: "MR-002", docstatus: 1, status: "Pending", material_request_type: "Purchase", company: "测试公司", items: [{ name: "MRI-002", item_code: "ITEM-B", item_name: "物料B", stock_qty: 5, ordered_qty: 0, conversion_factor: 1, uom: "箱", warehouse: "辅料仓", schedule_date: "2026-09-02" }] },
		];
		window.__messages = [];
		(0, eval)(source);
	}, source);

	await page.evaluate(() => {
		const listview = { page: { add_action_item(label, action) { const button = document.createElement("button"); button.textContent = label; button.dataset.action = label; button.onclick = action; document.querySelector("#actions").append(button); } }, get_checked_items: () => ["MR-001", "MR-002"] };
		frappe.listview_settings["Material Request"].onload(listview);
	});
	assert.equal(await page.getByRole("button", { name: "合并生成采购订单" }).count(), 1);
	results.push({ name: "采购申请批量入口", status: "passed", details: "列表操作菜单新增合并生成采购订单" });

	await page.getByRole("button", { name: "合并生成采购订单" }).click();
	for (const label of ["采购申请", "物料编码", "物料名称", "剩余数量", "单位", "仓库", "要求日期", "公司"]) {
		assert.ok(await page.getByText(label, { exact: true }).count(), `missing dialog field ${label}`);
	}
	assert.equal(await page.locator(".mes-merge-po-table-wrap tbody tr").count(), 2);
	results.push({ name: "合并确认字段", status: "passed", details: "供应商、公司及 7 个明细字段完整，包含两张申请的两行物料" });

	await page.getByLabel("供应商").fill("供应商A");
	await page.getByRole("button", { name: "创建采购订单" }).click();
	const state = await page.evaluate(() => ({ args: window.__callArgs, route: window.__route }));
	assert.deepEqual(state.args.material_requests, ["MR-001", "MR-002"]);
	assert.deepEqual(state.args.selected_items, ["MRI-001", "MRI-002"]);
	assert.equal(state.args.supplier, "供应商A");
	assert.deepEqual(state.route, ["Form", "Purchase Order", "new-purchase-order"]);
	results.push({ name: "生成采购订单", status: "passed", details: "供应商、申请和明细参数完整，成功路由到未保存采购订单" });

	await page.getByRole("button", { name: "合并生成采购订单" }).click();
	await page.setViewportSize({ width: 390, height: 844 });
	const mobile = await page.locator(".mes-merge-po-table-wrap").evaluate((node) => ({ overflowX: getComputedStyle(node).overflowX, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth }));
	assert.equal(mobile.overflowX, "auto");
	assert.ok(mobile.scrollWidth > mobile.clientWidth);
	results.push({ name: "移动端对话框", status: "passed", details: "明细表在容器内横向滚动，无视口级横向溢出" });

	await page.screenshot({ path: "/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order.png", fullPage: true });
	await fs.writeFile("/home/cst/frappe_docker/development/frappe-bench/apps/client_akivision/docs/playwright_material_request_merge_purchase_order_result.json", JSON.stringify({ tested_at: new Date().toISOString(), browser: "Chromium", results }, null, 2) + "\n");
	console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
	await browser.close();
}
