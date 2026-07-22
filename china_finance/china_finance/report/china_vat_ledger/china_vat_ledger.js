frappe.query_reports["China VAT Ledger"] = {
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
};
