import frappe


def execute():
	"""Restore Frappe lifecycle docstatus from the service-state compatibility release."""
	if not frappe.db.exists("DocType", "China Cash Flow Assignment"):
		return
	for status, docstatus in (("Confirmed", 1), ("Cancelled", 2), ("Draft", 0)):
		frappe.db.set_value(
			"China Cash Flow Assignment",
			{"status": status},
			"docstatus",
			docstatus,
			update_modified=False,
		)
