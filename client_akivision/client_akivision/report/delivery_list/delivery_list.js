frappe.query_reports["Delivery List"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
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
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "item_code",
			label: __("Product Code"),
			fieldtype: "Link",
			options: "Item",
		},
	],
	tree: true,
	parent_field: "parent",
	name_field: "name",
	initial_depth: 2,
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "name" && data && data.name_display) {
			value = data.name_display;
		}
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname !== "order_status" || !value) return formatted;

		const indicator = {
			"草稿": "gray",
			"已冻结": "orange",
			"待送货和开票": "orange",
			"待开票": "orange",
			"待送货": "orange",
			"已完成": "green",
			"已取消": "red",
			"已关闭": "gray",
			"未关联销售订单": "blue",
		}[value] || "gray";
		return `<span class="indicator-pill ${indicator}">${frappe.utils.escape_html(value)}</span>`;
	},
	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
