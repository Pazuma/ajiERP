app_name = "draft_notifications"
app_title = "Draft Notifications"
app_publisher = "yuewei"
app_description = "Configurable draft document email notifications"
app_email = "308642281@qq.com"
app_license = "mit"

doc_events = {
	"*": {
		"after_insert": "draft_notifications.draft_notifications.draft_notification.handle_after_insert",
	},
}

scheduler_events = {
	"all": [
		"draft_notifications.draft_notifications.draft_notification.sync_queued_logs",
	],
}
