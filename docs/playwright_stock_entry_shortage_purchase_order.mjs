import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "../../../../erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps";
const script = await fs.readFile(
	`${appRoot}/mes_integration/mes_integration/public/js/stock_entry_shortage_dialog.js`,
	"utf8",
);
const browser = await chromium.launch({
	headless: true,
	executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
	args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

try {
	await page.setContent("<!doctype html><html lang=\"zh-CN\"><body></body></html>");
	await page.evaluate((source) => {
		window.__ = (value, args = []) => String(value).replace("{0}", args[0] || "");
		window.flt = (value) => Number(value || 0);
		window.$ = () => ({ on: () => {} });
		window.frappe = {
			datetime: { get_today: () => "2026-08-27" },
			model: {
				with_doctype: (_doctype, callback) => callback(),
				get_new_doc: () => (window.__purchaseRequest = {
					doctype: "Material Request",
					name: "new-material-request",
					items: [],
				}),
				add_child: (doc) => {
					const row = {};
					doc.items.push(row);
					return row;
				},
			},
			set_route: (...route) => {
				window.__route = route;
			},
		};

		const selection = (nodes) => ({
			addClass: (names) => {
				nodes.forEach((node) => node.classList.add(...names.split(" ")));
				return selection(nodes);
			},
			removeClass: (names) => {
				nodes.forEach((node) => node.classList.remove(...names.split(" ")));
				return selection(nodes);
			},
			find: (selector) => selection(nodes.flatMap((node) => [...node.querySelectorAll(selector)])),
			length: nodes.length,
		});

		window.__showStandardShortageDialog = () => {
			document.body.innerHTML = `
				<section id="stock-shortage-modal" class="modal show">
					<div class="modal-dialog">
						<div class="modal-content">
							<div class="modal-header"><h2>库存不足</h2><button id="close">关闭</button></div>
							<div class="modal-body msgprint"><p>为完成此交易，在仓库 原料仓 中的物料 RM-001 数量还缺 10.0。</p></div>
							<div class="modal-footer hide hidden"><button id="purchase-entry" class="btn-secondary hide hidden"></button></div>
						</div>
					</div>
				</section>`;
			const modal = document.querySelector("#stock-shortage-modal");
			window.frappe.msg_dialog = {
				$wrapper: {
					is: () => true,
					addClass: (names) => modal.classList.add(...names.split(" ")),
					text: () => modal.textContent,
					find: (selector) => selection([...modal.querySelectorAll(selector)]),
				},
				set_secondary_action_label(label) {
					document.querySelector("#purchase-entry").textContent = label;
				},
				set_secondary_action(action) {
					document.querySelector("#purchase-entry").onclick = action;
				},
				hide() {
					window.__standardDialogHidden = true;
				},
			};
		};

		window.cur_frm = {
			doctype: "Stock Entry",
			doc: {
				doctype: "Stock Entry",
				docstatus: 0,
				name: "MAT-STE-2026-00067",
				company: "测试公司",
				items: [{
					item_code: "RM-001",
					item_name: "主料",
					s_warehouse: "原料仓",
					qty: 70,
					uom: "个",
					stock_uom: "个",
					conversion_factor: 1,
				}],
			},
		};
		(0, eval)(source);
	}, script);

	await page.evaluate(() => window.__showStandardShortageDialog());
	await page.waitForTimeout(250);

	assert.equal(await page.getByRole("heading", { name: "库存不足" }).count(), 1);
	assert.equal(await page.getByText("发起采购申请", { exact: true }).count(), 1);
	assert.equal(await page.locator(".mes-stock-entry-shortage-dialog").count(), 1);
	assert.equal(await page.locator(".mes-stock-entry-shortage-modal").count(), 1);
	assert.equal(await page.locator(".mes-stock-entry-shortage-footer").count(), 1);
	assert.equal(await page.locator(".mes-stock-entry-purchase-btn").count(), 1);
	assert.equal(await page.locator("#purchase-entry").evaluate((button) => {
		const footer = button.closest(".modal-footer");
		return footer && !footer.classList.contains("hide") && !footer.classList.contains("hidden");
	}), true);

	await page.getByText("发起采购申请", { exact: true }).click();
	const created = await page.evaluate(() => ({
		route: window.__route,
		hidden: window.__standardDialogHidden,
		purchaseRequest: window.__purchaseRequest,
	}));
	assert.deepEqual(created.route, ["Form", "Material Request", "new-material-request"]);
	assert.equal(created.hidden, true);
	assert.equal(created.purchaseRequest.company, "测试公司");
	assert.equal(created.purchaseRequest.material_request_type, "Purchase");
	assert.equal(created.purchaseRequest.transaction_date, "2026-08-27");
	assert.equal(created.purchaseRequest.schedule_date, "2026-08-27");
	assert.deepEqual(created.purchaseRequest.items.map((row) => ({
		item_code: row.item_code,
		qty: row.qty,
		uom: row.uom,
		stock_uom: row.stock_uom,
		warehouse: row.warehouse,
		schedule_date: row.schedule_date,
	})), [{
		item_code: "RM-001",
		qty: 10,
		uom: "个",
		stock_uom: "个",
		warehouse: "原料仓",
		schedule_date: "2026-08-27",
	}]);

	await page.screenshot({ path: "/tmp/stock-entry-shortage-purchase-request-mobile.png", fullPage: true });
	console.log(JSON.stringify({
		status: "passed",
		checks: ["原生库存不足弹窗", "右下角采购申请入口", "采购申请草稿路由", "缺料字段回填", "窄屏按钮可见"],
	}, null, 2));
} finally {
	await browser.close();
}
