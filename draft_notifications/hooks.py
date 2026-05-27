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
}

scheduler_events = {
	"all": [
		"draft_notifications.draft_notifications.draft_notification.sync_queued_logs",
	],
}

override_whitelisted_methods = {
	"frappe.desk.doctype.notification_log.notification_log.get_notification_logs": "draft_notifications.notification_log.get_notification_logs",
}

