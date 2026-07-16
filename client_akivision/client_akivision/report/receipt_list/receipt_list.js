frappe.query_reports["Receipt List"] = {
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
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
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
			fieldname: "purchase_order",
			label: __("Purchase Order"),
			fieldtype: "Link",
			options: "Purchase Order",
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
