frappe.listview_settings["UOM"] = {
	formatters: {
		uom_name(value) {
			return frappe.boot.lang === "zh" ? __(value || "") : value;
		},
		category(value) {
			return frappe.boot.lang === "zh" ? __(value || "") : value;
		},
	},
};
