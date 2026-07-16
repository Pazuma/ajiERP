frappe.query_reports["Safety Stock Status"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company } } : {};
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nNormal\nWarning\nBelow Safety\nOver Max",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "status" || !value) return formatted;

		const indicator = {
			Normal: "green",
			Warning: "orange",
			"Below Safety": "red",
			"Over Max": "red",
			正常: "green",
			预警: "orange",
			低于安全库存: "red",
			超过上限: "red",
		}[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
