frappe.query_reports["Summary Calculation"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "internal_model",
			label: __("内部机种"),
			fieldtype: "Data",
		},
		{
			fieldname: "external_model",
			label: __("外部型号"),
			fieldtype: "Data",
		},
	],
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
};
