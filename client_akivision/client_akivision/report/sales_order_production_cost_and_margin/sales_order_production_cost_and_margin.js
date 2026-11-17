frappe.query_reports["Sales Order Production Cost and Margin"] = {
	filters: [
		{fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company"},
		{fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -1)},
		{fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today()},
		{fieldname: "sales_order", label: __("Sales Order"), fieldtype: "Link", options: "Sales Order"},
	],
};
