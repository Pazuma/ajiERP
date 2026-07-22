import frappe


def execute():
	"""Cash-flow confirmation uses a service state, not Frappe document submission."""
	if not frappe.db.exists("DocType", "China Cash Flow Assignment"):
		return
	frappe.db.set_value(
		"China Cash Flow Assignment",
		{"docstatus": ["in", [1, 2]]},
		"docstatus",
		0,
		update_modified=False,
	)
