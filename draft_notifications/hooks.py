app_name = "draft_notifications"
app_title = "Draft Notifications"
app_publisher = "yuewei"
app_description = "Configurable draft document email notifications"
app_email = "308642281@qq.com"
app_license = "mit"

app_include_js = "/assets/draft_notifications/js/notification_badge.js?v=2026052706"

doc_events = {
	"*": {
		"after_insert": "draft_notifications.draft_notifications.draft_notification.handle_after_insert",
		"on_update": "draft_notifications.draft_notifications.draft_notification.handle_on_update",
		"on_submit": "draft_notifications.draft_notifications.draft_notification.handle_on_submit",
		"on_cancel": "draft_notifications.draft_notifications.draft_notification.handle_on_cancel",
	},
	"Purchase Receipt": {
		"on_submit": "draft_notifications.draft_notifications.draft_notification.handle_purchase_receipt_submit",
		"on_cancel": "draft_notifications.draft_notifications.draft_notification.handle_purchase_receipt_cancel",
	},
	# Item creation can be completed through Item-specific flows that do not
	# consistently reach the wildcard hook. Keep an explicit hook so an
	# After Insert rule for Item is always queued.
	"Item": {
		"after_insert": "draft_notifications.draft_notifications.draft_notification.handle_item_after_insert",
	},
}

scheduler_events = {
	"all": [
		"draft_notifications.draft_notifications.draft_notification.sync_queued_logs",
		"draft_notifications.draft_notifications.draft_notification.process_date_condition_notifications",
	],
}

override_whitelisted_methods = {
	"frappe.desk.doctype.notification_log.notification_log.get_notification_logs": "draft_notifications.notification_log.get_notification_logs",
}
