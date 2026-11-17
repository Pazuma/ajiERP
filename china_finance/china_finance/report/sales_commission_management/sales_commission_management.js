frappe.query_reports["Sales Commission Management"] = {
	filters: [
		{fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", reqd: 1, default: frappe.defaults.get_user_default("Company")},
		{fieldname: "sales_order", label: __("销售订单"), fieldtype: "Link", options: "Sales Order"},
		{fieldname: "customer", label: __("客户"), fieldtype: "Link", options: "Customer"},
	],
	onload(report) {
		if (frappe.session.user === "Administrator" || (frappe.user_roles || []).some(role => ["销售总监", "Sales Commission Manager"].includes(role))) {
			report.page.add_inner_button(__("维护提成单"), () => frappe.set_route("List", "Sales Commission Sheet"));
		}
	},
};
