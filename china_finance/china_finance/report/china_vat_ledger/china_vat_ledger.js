frappe.query_reports["China VAT Ledger"] = {
	filters: [
		{ fieldname: "company", fieldtype: "Link", label: __("公司"), options: "Company", reqd: 1 },
		{ fieldname: "from_date", fieldtype: "Date", label: __("起始日期"), reqd: 1 },
		{ fieldname: "to_date", fieldtype: "Date", label: __("截止日期"), reqd: 1 },
		{ fieldname: "direction", fieldtype: "Select", label: __("进销项"), options: "\n销项\n进项" },
		{ fieldname: "invoice_status", fieldtype: "Select", label: __("票据状态"), options: "\n蓝票\n红票\n作废" },
		{ fieldname: "exclude_void", fieldtype: "Check", label: __("排除作废"), default: 0 },
	],
	onload(report) {
		if (!report.get_filter_value("company")) {
			report.set_filter_value("company", frappe.defaults.get_user_default("Company"));
		}
	},
};
