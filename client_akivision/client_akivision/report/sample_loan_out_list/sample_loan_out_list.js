frappe.query_reports["Sample Loan Out List"] = {
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
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
			default: frappe.datetime.year_end(),
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
	],
	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 2,
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "name" && data.indent === 1 && data.item_code) {
			return default_formatter(data.item_code, row, column, data);
		}
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "status" || !value) return formatted;

		const indicator = {
			"已借出": "orange",
			"已归还": "green",
			"已转销售": "blue",
			"Borrowed": "orange",
			"Returned": "green",
			"Converted to Sales": "blue",
		}[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
