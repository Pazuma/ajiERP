frappe.query_reports["Finished Goods Inventory"] = {
	filters: [{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company"), reqd: 1 }],
};
