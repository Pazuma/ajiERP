frappe.query_reports["Finished Goods Status"] = {
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
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\n借出样品\n样品\n销售品",
		},
		{
			fieldname: "sub_status",
			label: __("Sub Status"),
			fieldtype: "Select",
			options: "\n已借出\nfor-sample\n已销售\n转销售\n旧款",
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
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!value || !["status", "sub_status"].includes(column.fieldname)) {
			return formatted;
		}

		const color_map =
			column.fieldname === "status"
				? {
						"借出样品": "blue",
						"样品": "yellow",
						"销售品": "green",
				  }
				: {
						"已借出": "blue",
						"for-sample": "yellow",
						"已销售": "green",
						"转销售": "purple",
						"旧款": "grey",
				  };

		const color = color_map[value] || "grey";
		return `<span class="indicator-pill ${color} no-indicator-dot ellipsis"><span class="ellipsis">${frappe.utils.escape_html(value)}</span></span>`;
	},

	get_datatable_options(options) {
		return { ...options, cellHeight: 38 };
	},
};
