import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class ChinaPurchaseReconciliationRule(Document):
	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		if flt(self.amount_tolerance) < 0 or flt(self.quantity_tolerance) < 0:
			frappe.throw(_("对账容差不能小于零"))
