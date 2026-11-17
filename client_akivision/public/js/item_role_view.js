(function () {
	const policies = {
		purchase: { tabs: ["details", "purchasing_tab", "dashboard_tab"], links: ["Material Request", "Request for Quotation", "Supplier Quotation", "Purchase Order", "Purchase Receipt"] },
		stock: { tabs: ["details", "inventory_section", "dashboard_tab"], links: ["Purchase Receipt", "Delivery Note", "Stock Entry", "Stock Reconciliation", "Batch", "Serial No"] },
	};
	function apply(frm) {
		frm._module_item_policy = policies[window.client_item_view];
		for (const tab of frm.layout?.tabs || []) {
			if (!tab._module_view_wrapped) {
				const refresh = tab.refresh.bind(tab);
				const activate = tab.set_active.bind(tab);
				tab.refresh = function () {
					refresh();
					if (frm._module_item_policy && !frm._module_item_policy.tabs.includes(this.df.fieldname)) this.toggle(false);
				};
				tab.set_active = function () {
					if (!frm._module_item_policy || frm._module_item_policy.tabs.includes(this.df.fieldname)) return activate();
					frm.layout.tabs.find((entry) => !entry.is_hidden())?.set_active();
				};
				tab._module_view_wrapped = true;
			}
			tab.refresh();
		}
		const active = frm.layout?.tabs.find((tab) => tab.is_active());
		if (active?.is_hidden()) frm.layout.tabs.find((tab) => !tab.is_hidden())?.set_active();
		const dashboard = frm.dashboard;
		if (!dashboard?.data) return;
		// Reconstruct from metadata rather than from a previously cropped instance.
		const { frm: ignored_form, ...source } = frm.meta.__dashboard || {};
		dashboard.data = JSON.parse(JSON.stringify(source));
		dashboard.filter_permissions();
		const policy = frm._module_item_policy;
		if (policy) {
			dashboard.data.transactions = (dashboard.data.transactions || []).map((group) => ({ ...group, items: group.items.filter((dt) => policy.links.includes(dt)) })).filter((group) => group.items.length);
			dashboard.data.reports = [];
			dashboard.data.heatmap = false;
		}
		dashboard.transactions_area.empty();
		dashboard.data_rendered = false;
		dashboard.refresh();
	}
	frappe.ui.form.on("Item", { refresh: apply });
	if (typeof module !== "undefined") module.exports = { policies };
})();
