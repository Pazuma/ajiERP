const assert = require("node:assert/strict");
let events;
global.window = { client_item_view: "purchase" };
global.frappe = { ui: { form: { on: (_dt, handlers) => { events = handlers; } } } };
require("../item_role_view.js");
const tabs = ["details", "purchasing_tab", "inventory_section", "sales_tab", "dashboard_tab"].map(fieldname => ({
	df: { fieldname }, hidden: false, active: fieldname === "sales_tab",
	refresh() { this.hidden = false; }, toggle(show) { this.hidden = !show; },
	is_hidden() { return this.hidden; }, is_active() { return this.active; }, set_active() { this.active = true; },
}));
const meta = { __dashboard: { transactions: [{ label: "Buy", items: ["Purchase Order", "Purchase Invoice"] }, { label: "Stock", items: ["Stock Entry"] }], heatmap: true } };
const frm = { layout: { tabs }, meta, dashboard: { data: {}, filter_permissions() {}, transactions_area: { empty() {} }, refresh() {} } };
events.refresh(frm);
assert.equal(tabs[2].hidden, true);
assert.deepEqual(frm.dashboard.data.transactions[0].items, ["Purchase Order"]);
window.client_item_view = "stock";
events.refresh(frm);
assert.equal(tabs[1].hidden, true);
assert.equal(tabs[2].hidden, false);
assert.deepEqual(frm.dashboard.data.transactions[0].items, ["Stock Entry"]);
window.client_item_view = "full";
events.refresh(frm);
assert.equal(tabs.every(tab => !tab.hidden), true);
assert.equal(frm.dashboard.data.transactions.length, 2);
window.client_item_view = null;
events.refresh(frm);
assert.equal(tabs.every(tab => !tab.hidden), true);
assert.equal(meta.__dashboard.transactions[0].items.length, 2);
console.log("Module Item views: assertions passed");
