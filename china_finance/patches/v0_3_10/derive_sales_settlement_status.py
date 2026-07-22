import frappe


def execute():
	"""Derive the draft display status from the confirmation method on existing settlements."""
	if not frappe.db.exists("DocType", "China Sales Settlement"):
		return

	frappe.db.set_value(
		"China Sales Settlement",
		{"docstatus": 0, "status": "草稿", "confirmation_method": "外部客户确认"},
		"status",
		"待客户确认",
		update_modified=False,
	)
	frappe.db.set_value(
		"China Sales Settlement",
		{"docstatus": 0, "status": "草稿", "confirmation_method": "内部复核"},
		"status",
		"待内部复核",
		update_modified=False,
	)
