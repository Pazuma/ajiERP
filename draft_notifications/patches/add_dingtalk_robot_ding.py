import frappe


def execute():
	for doctype in (
		"dingtalk_robot_recipient",
		"dingtalk_robot_config",
		"draft_notification_rule",
		"draft_notification_log",
	):
		frappe.reload_doc("draft_notifications", "doctype", doctype, force=True)
