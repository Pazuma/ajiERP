const native_material_request_listview = frappe.listview_settings["Material Request"] || {};

frappe.listview_settings["Material Request"] = {
	...native_material_request_listview,
	onload(listview) {
		if (typeof native_material_request_listview.onload === "function") {
			native_material_request_listview.onload(listview);
		}
		// Purchase is the default entry point for the Buying workspace. Users can
		// still remove or change this filter in the list view.
		const filters = listview.filter_area.get() || [];
		const has_purpose_filter = filters.some(
			(filter) => filter[1] === "material_request_type" || filter[0] === "material_request_type"
		);
		if (!has_purpose_filter) {
			listview.filter_area.add([["Material Request", "material_request_type", "=", "Purchase"]]);
		}
	},
};
