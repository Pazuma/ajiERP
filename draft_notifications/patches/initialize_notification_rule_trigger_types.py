import frappe


def execute():
	"""Backfill the trigger type for existing notification rules."""
	if not frappe.db.exists("DocType", "Draft Notification Rule"):
		return

	frappe.reload_doc("draft_notifications", "doctype", "draft_notification_rule", force=True)

	frappe.db.sql(
		"""
		update `tabDraft Notification Rule`
		set trigger_type = 'Document Event'
		where ifnull(trigger_type, '') = ''
		"""
	)
