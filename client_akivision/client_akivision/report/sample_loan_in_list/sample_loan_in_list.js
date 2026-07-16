frappe.query_reports["Sample Loan In List"] = {
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
		// `name` is an internal unique tree key (SLI-...#row). Render the
		// business value instead: loan number for parents, supplier model for
		// borrowed-sample leaves.
		if (column.fieldname === "name" && data?.name_display) {
			return default_formatter(data.name_display, row, column, data);
		}
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "status" || !value) return formatted;

		const indicator = {
			"已借入": "blue",
			"借用中": "blue",
			"部分归还": "orange",
			"已归还": "green",
			"Borrowed": "blue",
			"Partially Returned": "orange",
			"Returned": "green",
		}[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
