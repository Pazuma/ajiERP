import frappe
from frappe import _
from frappe.model.document import Document


class AgingPeriodRule(Document):
	def validate(self):
		if self.to_days and self.to_days < self.from_days:
			frappe.throw(_("截止天数不能小于起始天数。"))
