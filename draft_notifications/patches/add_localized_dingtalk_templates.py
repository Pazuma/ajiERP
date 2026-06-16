import frappe


def execute():
	frappe.reload_doc("draft_notifications", "doctype", "draft_notification_rule", force=True)
