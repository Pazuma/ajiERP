frappe.listview_settings["Purchase Comparison"] = {
	get_indicator(doc) {
		const status_colors = {
			Draft: "red",
			Compared: "blue",
			"PO Created": "green",
		};
		return [__(doc.status), status_colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
