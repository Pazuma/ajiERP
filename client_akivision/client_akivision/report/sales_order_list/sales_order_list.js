(function () {
	// Frappe 原生报表摘要只支持 green / red / blue，补充 orange 样式
	if (!document.getElementById("sales-order-list-summary-style")) {
		$(
			`<style id="sales-order-list-summary-style">
				.report-summary .summary-value.orange { color: var(--orange-500, #e86c13); }
			</style>`
		).appendTo(document.head);
	}

	frappe.query_reports["Sales Order List"] = {
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
			fieldname: "sales_person",
			label: __("Sales Person"),
			fieldtype: "Link",
			options: "Sales Person",
		},
		{
			fieldname: "status",
			label: __("Order Status"),
			fieldtype: "Select",
			options: "\n未交货\n交货中\n已交货\n未开票\n部分开票\n已开票\n未付款\n部分收款\n已付款\n待开票\n待收款\n已完成",
		},
		{
			fieldname: "is_high_tech",
			label: __("High-tech Revenue"),
			fieldtype: "Select",
			options: "\n是\n否",
		},
	],
	tree: true,
	name_field: "name",
	parent_field: "parent",
	initial_depth: 2,
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "name" && data.indent === 1) {
			return frappe.utils.escape_html(data.item_name || data.item_code || "");
		}

		const formatted = default_formatter(value, row, column, data);
		if (!value || !["completion_status", "invoice_status", "collection_status", "final_status", "completion_flag", "item_completed", "order_fully_completed", "is_high_tech"].includes(column.fieldname)) {
			return formatted;
		}

		const indicator = {
			"已交货": "green",
			"交货中": "orange",
			"未交货": "red",
			"已开票": "green",
			"部分开票": "orange",
			"未开票": "red",
			"已付款": "green",
			"部分收款": "orange",
			"未付款": "red",
			"未收款": "red",
			"待开票": "orange",
			"待收款": "orange",
			"已完成": "green",
			"未完成": "orange",
			"是": "green",
			"否": "orange",
		}[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
})();
