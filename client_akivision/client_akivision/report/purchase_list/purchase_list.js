frappe.query_reports["Purchase List"] = {
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
	],
	tree: true,
	parent_field: "parent",
	name_field: "name",
	initial_depth: 2,
	formatter: function (value, row, column, data, default_formatter) {
		if (column.fieldname === "name" && data && data.name_display) {
			value = data.name_display;
		}
		if (column.fieldname === "reconciled_status" && data && data.reconciled_status) {
			const color_map = { 已对账: "green", 未对账: "orange" };
			const color = color_map[data.reconciled_status] || "gray";
			return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(
				__(data.reconciled_status)
			)}</span></span>`;
		}
		return default_formatter(value, row, column, data);
	},
};
