import frappe


def execute():
	"""Reload the customer-facing trigger field order and labels idempotently."""
	if frappe.db.exists("DocType", "Draft Notification Rule"):
		frappe.reload_doc("draft_notifications", "doctype", "draft_notification_rule", force=True)
