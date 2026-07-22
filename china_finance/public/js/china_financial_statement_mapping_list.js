frappe.listview_settings["China Financial Statement Mapping"] = {
	get_indicator(doc) {
		if (!doc.reviewed) return [__("待复核"), "orange", "reviewed,=,0"];
		return [__("已复核"), "green", "reviewed,=,1"];
	},
	onload(listview) {
		listview.page.add_inner_button(__("查看待复核映射"), () => {
			listview.filter_area.add([["China Financial Statement Mapping", "reviewed", "=", 0]]);
			listview.refresh();
		});
	},
};
