frappe.listview_settings["China Financial Statement Template"] = {
	onload(listview) {
		const filters = listview.filter_area.get();
		if (!filters.some((filter) => filter[1] === "effective_to")) {
			listview.filter_area.add([["China Financial Statement Template", "effective_to", "is", "not set"]]);
		}
	},
};
