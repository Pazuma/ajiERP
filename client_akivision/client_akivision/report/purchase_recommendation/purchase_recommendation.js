frappe.query_reports["Purchase Recommendation"] = {
	filters: [
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
			reqd: 1,
		},
		{
			fieldname: "qty",
			label: __("Demanded Qty"),
			fieldtype: "Float",
			default: 1,
			reqd: 1,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
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
		if (!data) {
			return formatted;
		}
		if (column.fieldname === "savings" && flt(data.savings) > 0) {
			return `<span style="color: var(--green-600); font-weight: 600;">${formatted}</span>`;
		}
		if (column.fieldname === "recommended" && value) {
			return `<span style="font-size: 14px;">${formatted}</span>`;
		}
		return formatted;
	},
};
