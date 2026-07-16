frappe.query_reports["Purchase Delay Analysis"] = {
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
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!value || column.fieldname !== "risk_level") {
			return formatted;
		}

		const color_map = {
			"Low Risk": "green",
			"Medium Risk": "orange",
			"High Risk": "red",
		};
		const color = color_map[value] || "gray";
		return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(__(value))}</span></span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
