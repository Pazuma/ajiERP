import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ChinaSalesSettlementRule(Document):
	def validate(self):
		self.rule_key = "|".join((self.company or "", self.customer or "", str(self.effective_from or "")))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
