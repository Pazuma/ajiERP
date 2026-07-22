frappe.query_reports["China Purchase Document Chain"] = {
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
};
