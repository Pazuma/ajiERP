// Extend (not replace) ERPNext's native Supplier Quotation list settings: keep
// its indicator and bulk actions, add the tier-price sync status pill.
const base_supplier_quotation_listview = frappe.listview_settings["Supplier Quotation"] || {};

frappe.listview_settings["Supplier Quotation"] = {
	...base_supplier_quotation_listview,
	add_fields: [...(base_supplier_quotation_listview.add_fields || []), "custom_tier_sync_status"],
	get_indicator(doc) {
		if (doc.custom_tier_sync_status === "Synced") {
			return [__("Synced"), "green", "custom_tier_sync_status,=,Synced"];
		}
		if (doc.custom_tier_sync_status === "Sync Failed") {
			return [__("Sync Failed"), "red", "custom_tier_sync_status,=,Sync Failed"];
		}
		return base_supplier_quotation_listview.get_indicator
			? base_supplier_quotation_listview.get_indicator(doc)
			: undefined;
	},
};
