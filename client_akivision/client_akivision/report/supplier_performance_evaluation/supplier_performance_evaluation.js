frappe.query_reports["Supplier Performance Evaluation"] = {
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "supplier_rating" || !value) return formatted;

		const indicator = { "A级": "blue", "B级": "green", "C级": "orange", "D级": "red" }[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
