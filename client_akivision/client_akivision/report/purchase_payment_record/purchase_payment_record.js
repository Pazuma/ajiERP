frappe.query_reports["Purchase Payment Record"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 },
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.year_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.year_end() },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "payment_category" && data.payment_category) {
			return `<span class="indicator-pill blue no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(data.payment_category)}</span></span>`;
		}
		return value;
	},
	get_datatable_options(options) {
		return Object.assign(options, { cellHeight: 38, dynamicRowHeight: true });
	},
};
