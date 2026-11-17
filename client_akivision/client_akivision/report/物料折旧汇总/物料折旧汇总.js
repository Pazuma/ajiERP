frappe.query_reports["物料折旧汇总"] = {
	filters: [
		{
			fieldname: "company", label: "公司", fieldtype: "Link", options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			on_change(report) {
				if (report.get_filter_value("warehouse")) {
					report.set_filter_value("warehouse", "");
				} else {
					report.refresh();
				}
			},
		},
		{
			fieldname: "warehouse", label: "仓库", fieldtype: "Link", options: "Warehouse",
			get_query() {
				const company = frappe.query_report.get_filter_value("company");
				return { filters: { is_group: 0, disabled: 0, ...(company ? { company } : {}) } };
			},
		},
		{
			fieldname: "item_code", label: "物料", fieldtype: "Link", options: "Item",
			get_query: () => ({ filters: { disabled: 0, is_stock_item: 1 } }),
		},
		{
			fieldname: "only_in_stock", label: "库存范围", fieldtype: "Select", default: "1",
			// Query Report omits unchecked Check filters; string "0" survives serialization.
			options: [{ label: "仅有库存", value: "1" }, { label: "包含零库存", value: "0" }],
		},
	],
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "last_usage_time" && !value) return "暂无有效使用记录";
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname === "item_code" && data) {
			const title = frappe.utils.escape_html(`${data.item_name || ""} / ${data.warehouse || ""}`);
			return `<span title="${title}">${formatted}</span>`;
		}
		return formatted;
	},
};
