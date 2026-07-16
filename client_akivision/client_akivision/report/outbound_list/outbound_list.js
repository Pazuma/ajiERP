frappe.query_reports["Outbound List"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "stock_entry_type",
			label: __("Stock Entry Type"),
			fieldtype: "Link",
			options: "Stock Entry Type",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
		},
	],
	tree: true,
	parent_field: "parent",
	name_field: "name",
	initial_depth: 2,
	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "name" && data && data.name_display) {
			value = data.name_display;
		}
		return default_formatter(value, row, column, data);
	},
};
