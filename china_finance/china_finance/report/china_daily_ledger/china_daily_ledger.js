frappe.query_reports["China Daily Ledger"] = {
	filters: [
		{ fieldname: "company", label: __("公司"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 },
		{ fieldname: "finance_book", label: __("账簿"), fieldtype: "Link", options: "Finance Book" },
		{
			fieldname: "month",
			label: __("月份"),
			fieldtype: "Data",
			default: frappe.datetime.get_today().slice(0, 7),
			on_change() {
				const month = frappe.query_report.get_filter_value("month");
				if (!/^\\d{4}-\\d{2}$/.test(month || "")) return;
				frappe.query_report.set_filter_value("from_date", `${month}-01`);
				frappe.query_report.set_filter_value("to_date", frappe.datetime.month_end(`${month}-01`));
			},
		},
		{ fieldname: "from_date", label: __("开始日期"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_start() },
		{ fieldname: "to_date", label: __("结束日期"), fieldtype: "Date", reqd: 1, default: frappe.datetime.month_end() },
		{ fieldname: "account", label: __("科目"), fieldtype: "MultiSelectList", options: "Account" },
		{ fieldname: "voucher_no", label: __("凭证号"), fieldtype: "Data" },
		{ fieldname: "keyword", label: __("关键词"), fieldtype: "Data" },
		{ fieldname: "show_daily_subtotal", label: __("显示本日小计"), fieldtype: "Check" },
	],
	onload(report) {
		report.page.wrapper.addClass("cf-daily-ledger");
	},
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		return data && data.row_kind && column.fieldname === "remarks"
			? `<span class="cf-daily-ledger-${data.row_kind}">${formatted}</span>`
			: formatted;
	},
};
