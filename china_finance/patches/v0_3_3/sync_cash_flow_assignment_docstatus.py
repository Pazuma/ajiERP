import frappe


def execute():
	if not frappe.db.exists("DocType", "China Cash Flow Assignment"):
		return

	frappe.db.set_value(
		"China Cash Flow Assignment",
		{"status": "Confirmed", "docstatus": 0},
		"docstatus",
		1,
		update_modified=False,
	)
	frappe.db.set_value(
		"China Cash Flow Assignment",
		{"status": "Cancelled", "docstatus": 0},
		"docstatus",
		2,
		update_modified=False,
	)
