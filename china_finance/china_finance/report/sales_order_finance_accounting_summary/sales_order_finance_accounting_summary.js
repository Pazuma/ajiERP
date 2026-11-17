frappe.query_reports["Sales Order Finance Accounting Summary"] = {
	filters: [
		{fieldname:"company",label:__("公司"),fieldtype:"Link",options:"Company",reqd:1,default:frappe.defaults.get_user_default("Company")},
		{fieldname:"from_date",label:__("核算开始日期"),fieldtype:"Date"},
		{fieldname:"to_date",label:__("核算结束日期"),fieldtype:"Date"},
		{fieldname:"customer",label:__("客户"),fieldtype:"Link",options:"Customer"},
		{fieldname:"sales_order",label:__("销售订单"),fieldtype:"Link",options:"Sales Order"},
		{fieldname:"sales_invoice",label:__("销售发票"),fieldtype:"Link",options:"Sales Invoice"},
		{fieldname:"status",label:__("核算状态"),fieldtype:"Select",options:"\n草稿\n已确认\n待复核"},
	],
	formatter(value, row, column, data, default_formatter) {
		if (["base_revenue", "base_sales_cost", "base_tax", "base_gross_profit", "gross_margin"].includes(column.fieldname) && data?.[column.fieldname] == null) return "";
		return default_formatter(value, row, column, data);
	},
};
