frappe.query_reports["Sales Commission Summary"] = {
	filters: [
	{
		"fieldname": "company",
		"label": "公司",
		"fieldtype": "Link",
		"options": "Company",
		"reqd": 1
	},
	{
		"fieldname": "mode",
		"label": "统计口径",
		"fieldtype": "Select",
		"options": "当前累计\n期间计提变动\n期间实际发放",
		"default": "当前累计"
	},
	{
		"fieldname": "sales_person",
		"label": "业务人员",
		"fieldtype": "Link",
		"options": "Sales Person"
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
	},
	{
		"fieldname": "from_date",
		"label": "开始日期",
		"fieldtype": "Date"
	},
	{
		"fieldname": "to_date",
		"label": "结束日期",
		"fieldtype": "Date"
	}
],
	onload(report) {
		if (!report.get_filter_value("company")) report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
	},
};

