import frappe


def execute():
	for doctype in (
		"dingtalk_robot_config",
		"draft_notification_rule",
		"draft_notification_log",
	):
		frappe.reload_doc("draft_notifications", "doctype", doctype, force=True)

	rename_channel("DingTalk DING", "DingTalk Private Chat")
	rename_channel("Email + DingTalk DING", "Email + DingTalk Private Chat")
	rename_channel("Desk + DingTalk DING", "Desk + DingTalk Private Chat")


def rename_channel(old, new):
	frappe.db.set_value(
		"Draft Notification Rule",
		{"notification_channel": old},
		"notification_channel",
		new,
		update_modified=False,
	)
