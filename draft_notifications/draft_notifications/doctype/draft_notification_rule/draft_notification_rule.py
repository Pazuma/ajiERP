from frappe.model.document import Document

from draft_notifications.draft_notifications.draft_notification import validate_custom_method


class DraftNotificationRule(Document):
	def validate(self):
		if self.recipient_type == "Custom Method":
			validate_custom_method(self.custom_method)
