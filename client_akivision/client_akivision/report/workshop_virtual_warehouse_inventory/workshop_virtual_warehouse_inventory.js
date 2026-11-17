frappe.query_reports["Workshop Virtual Warehouse Inventory"] = {
	filters: [{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 }],
};
