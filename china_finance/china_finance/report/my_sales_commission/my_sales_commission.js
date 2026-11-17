frappe.query_reports["My Sales Commission"] = {
	filters: [
	{
		"fieldname": "company",
		"label": "公司",
		"fieldtype": "Link",
		"options": "Company",
		"reqd": 1
	},
	{
		"fieldname": "sales_order",
		"label": "销售订单",
		"fieldtype": "Link",
		"options": "Sales Order"
	},
	{
		"fieldname": "customer",
		"label": "客户",
		"fieldtype": "Link",
		"options": "Customer"
	}
],
	onload(report) {
		if (!report.get_filter_value("company")) report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
	},
};

