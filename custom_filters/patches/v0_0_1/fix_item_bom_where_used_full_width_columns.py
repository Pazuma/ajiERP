import frappe


def execute():
	name = frappe.db.get_value(
		"Custom Field",
		{"dt": "Item", "fieldname": "custom_cf_bom_where_used_html"},
		"name",
	)
	if name:
		frappe.db.set_value("Custom Field", name, "columns", 0, update_modified=False)
		frappe.clear_cache(doctype="Item")
