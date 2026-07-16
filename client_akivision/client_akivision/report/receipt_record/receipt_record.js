frappe.query_reports["Receipt Record"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.year_start() },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.year_end() },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "receipt_status") {
			const color = { "已结清": "green", "未结清": "orange", "未关联销售发票": "red" }[data.receipt_status] || "gray";
			return indicator_pill(data.receipt_status, color);
		}
		if (column.fieldname === "is_invoiced") {
			return indicator_pill(data.is_invoiced, data.is_invoiced === "已开票" ? "blue" : "gray");
		}
		return value;
	},
	get_datatable_options(options) {
		return Object.assign(options, { cellHeight: 38, dynamicRowHeight: true });
	},
};

function indicator_pill(label, color) {
	if (!label) return "";
	return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(label)}</span></span>`;
}
