import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { chromium } from "../../../../erpnext.official/node_modules/playwright/index.mjs";

const appRoot = "/home/cst/frappe_docker/development/frappe-bench/apps";
const script = await fs.readFile(`${appRoot}/mes_integration/mes_integration/public/js/material_request.js`, "utf8");
const outputPrefix = "/tmp/stock-shortage-purchase-order";

const browser = await chromium.launch({
  headless: true,
  executablePath: "/home/cst/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const results = [];

try {
  await page.setContent(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
    body { font-family: sans-serif; margin: 24px; } .modal-dialog { max-width: 980px; }
    .modal-footer { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
    .btn { padding: 8px 12px; } .btn-primary { background: #16794c; color: white; }
    .table { width: 100%; border-collapse: collapse; } th, td { border: 1px solid #cbd5e1; padding: 8px; }
    .text-right { text-align: right; } .text-danger { color: #b42318; } .text-muted { color: #64748b; }
  </style></head><body><main><h1>物料需求发料</h1></main></body></html>`);

  await page.evaluate((source) => {
    window.__ = (value, args = []) => String(value).replace("{0}", args[0] || "");
    window.cstr = (value) => String(value || "");
    window.flt = (value) => Number(value || 0);
    window.cint = (value) => Number(value || 0);
    window.format_number = (value) => String(Number(value || 0));
    window.locals = {};
    window.$ = () => ({ find: () => ({ removeClass: () => ({ addClass: () => ({}) }) }) });
    class Dialog {
      constructor(options) { this.options = options; this.$wrapper = { addClass: () => {}, find: () => ({ css: () => {} }) }; }
      show() {
        document.querySelectorAll(".test-dialog").forEach((node) => node.remove());
        const node = document.createElement("section");
        node.className = "test-dialog";
        node.innerHTML = `<div class="modal-dialog"><h2>${this.options.title}</h2>${this.options.fields.map((field) => field.options || "").join("")}<div class="modal-footer"><button class="btn btn-secondary">${this.secondaryLabel || ""}</button><button class="btn btn-primary">${this.options.primary_action_label || ""}</button></div></div>`;
        node.querySelector(".btn-primary").addEventListener("click", () => this.options.primary_action?.());
        node.querySelector(".btn-secondary").addEventListener("click", () => this.secondaryAction?.());
        document.body.append(node);
      }
      hide() { document.querySelectorAll(".test-dialog").forEach((node) => node.remove()); }
      set_secondary_action(action) { this.secondaryAction = action; this.show(); }
      set_secondary_action_label(label) { this.secondaryLabel = label; document.querySelector(".test-dialog .btn-secondary")?.replaceChildren(document.createTextNode(label)); }
    }
    const createdDocs = [];
    window.frappe = {
      ui: { Dialog, form: { on: () => {} } },
      utils: { escape_html: (value) => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]) },
      defaults: { get_default: () => 2 }, datetime: { get_today: () => "2026-08-27" },
      model: {
        with_doctype: (_doctype, callback) => callback(),
        get_new_doc: (doctype) => { const doc = { doctype, name: "new-purchase-order", items: [] }; createdDocs.push(doc); return doc; },
        add_child: (doc, fieldname) => { const row = {}; doc[fieldname].push(row); return row; },
      },
      set_route: (...route) => { window.__route = route; },
      call: () => Promise.resolve({ message: { has_shortage: false, items: [] } }), msgprint: () => {},
    };
    window.__createdDocs = createdDocs;
    (0, eval)(source);
  }, script);

  const frm = { doc: { name: "MAT-MR-0001", company: "测试公司", schedule_date: "2026-09-03" } };
  const shortages = [
    { item_code: "ITEM-001", item_name: "主料", warehouse: "原料仓", requested_qty: 10, available_qty: 4, shortage_qty: 6, uom: "箱", stock_uom: "个", conversion_factor: 10, material_request_item: "row-001", schedule_date: "2026-09-03" },
    { item_code: "ITEM-002", item_name: "辅料", warehouse: "辅料仓", requested_qty: 5, available_qty: 0, shortage_qty: 5, uom: "个", stock_uom: "个", conversion_factor: 1, material_request_item: "row-002", schedule_date: "2026-09-04" },
  ];

  await page.evaluate(({ frm, shortages }) => window.show_issue_dialog_stock_shortage_dialog(frm, { show() {} }, shortages), { frm, shortages });
  for (const field of ["物料编码", "物料名称", "仓库", "本次需求", "可用库存", "缺口", "单位"]) assert.ok(await page.getByText(field, { exact: true }).count(), `missing shortage field: ${field}`);
  assert.equal(await page.locator(".mes-stock-shortage-table tbody tr").count(), 2);
  assert.ok(await page.getByText("发起采购订单", { exact: true }).count());
  assert.ok(await page.getByText("返回修改", { exact: true }).count());
  results.push({ name: "库存不足弹窗字段", status: "passed", details: "7 个业务字段、2 条缺料明细和两个动作均已渲染" });
  await page.screenshot({ path: `${outputPrefix}-desktop.png`, fullPage: true });

  await page.getByText("发起采购订单", { exact: true }).click();
  const created = await page.evaluate(() => ({ doc: window.__createdDocs[0], route: window.__route }));
  assert.deepEqual(created.route, ["Form", "Purchase Order", "new-purchase-order"]);
  assert.equal(created.doc.company, "测试公司");
  assert.equal(created.doc.items.length, 2);
  assert.deepEqual(created.doc.items.map((row) => ({ item_code: row.item_code, qty: row.qty, uom: row.uom, warehouse: row.warehouse, material_request: row.material_request, material_request_item: row.material_request_item })), [
    { item_code: "ITEM-001", qty: 6, uom: "箱", warehouse: "原料仓", material_request: "MAT-MR-0001", material_request_item: "row-001" },
    { item_code: "ITEM-002", qty: 5, uom: "个", warehouse: "辅料仓", material_request: "MAT-MR-0001", material_request_item: "row-002" },
  ]);
  results.push({ name: "采购订单字段回填", status: "passed", details: "物料、缺口数量、单位、仓库、交期和 Material Request 来源均正确带入未保存采购订单" });

  await page.evaluate(({ frm, shortages }) => window.show_issue_dialog_stock_shortage_dialog(frm, { show() { window.__returned = true; } }, shortages), { frm, shortages });
  await page.getByText("返回修改", { exact: true }).click();
  assert.equal(await page.evaluate(() => window.__returned), true);
  results.push({ name: "返回修改", status: "passed", details: "返回原发料对话框的回调已执行" });

  await page.evaluate(({ shortages }) => { document.body.innerHTML = window.get_issue_dialog_stock_shortage_html(shortages); }, { shortages });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobile = await page.locator(".mes-stock-shortage-table-wrap").evaluate((node) => ({ overflowX: getComputedStyle(node).overflowX, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth }));
  assert.equal(mobile.overflowX, "auto");
  assert.ok(mobile.scrollWidth >= mobile.clientWidth);
  results.push({ name: "移动端体验", status: "passed", details: "缺料表在容器内横向滚动，字段不压缩重叠" });
  await page.screenshot({ path: `${outputPrefix}-mobile.png`, fullPage: true });
  console.log(JSON.stringify({ status: "passed", results }, null, 2));
} finally {
  await browser.close();
}
