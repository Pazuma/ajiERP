frappe.query_reports["RD Project List"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nOpen\nCompleted\nCancelled",
		},
		{
			fieldname: "project_type",
			label: __("Project Type"),
			fieldtype: "Link",
			options: "Project Type",
		},
		{
			fieldname: "technical_domain",
			label: __("Technical Domain"),
			fieldtype: "Data",
		},
		{
			fieldname: "project_leader",
			label: __("Project Leader"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!value || column.fieldname !== "status") {
			return formatted;
		}

		const color_map = {
			Open: "orange",
			Completed: "green",
			Cancelled: "red",
		};
		const color = color_map[value] || "gray";
		return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(__(value))}</span></span>`;
	},

	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
