frappe.query_reports["Supplier Performance Evaluation"] = {
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
		report.page.add_inner_button(__("Recalculate Ratings"), () => {
			frappe.call({
				method: "client_akivision.utils.supplier_rating.recalculate_supplier_ratings",
				freeze: true,
				freeze_message: __("Recalculating supplier ratings..."),
				callback(r) {
					frappe.show_alert({
						message: __("Updated ratings for {0} suppliers", [r.message.updated]),
						indicator: "green",
					});
					report.refresh();
				},
			});
		});
		report.page.add_inner_button(__("Rating History"), () => {
			frappe.set_route("List", "Supplier Rating Record");
		});
		report.page.add_inner_button(__("Rating Settings"), () => {
			frappe.set_route("Form", "Buying Settings");
		});
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
