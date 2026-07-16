import frappe
from frappe import _
from frappe.model.document import Document


class PurchaseDelayRiskRule(Document):
	def validate(self):
		if self.to_days and self.to_days < self.from_days:
			frappe.throw(_("To Days cannot be less than From Days."))
