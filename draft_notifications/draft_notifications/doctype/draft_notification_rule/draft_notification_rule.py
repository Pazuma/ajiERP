import frappe
from frappe.model.document import Document

from draft_notifications.draft_notifications.draft_notification import validate_custom_method


class DraftNotificationRule(Document):
	def validate(self):
		if self.recipient_type == "Custom Method":
			validate_custom_method(self.custom_method)

		if self.notification_channel in ("DingTalk Private Chat", "Email + DingTalk Private Chat", "Desk + DingTalk Private Chat", "DingTalk DING", "Email + DingTalk DING", "Desk + DingTalk DING"):
			if not self.dingtalk_config:
				frappe.throw("DingTalk Robot Config is required for DingTalk notification channels.")
