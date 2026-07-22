frappe.query_reports["China Output Invoice Reconciliation"] = {
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
};
