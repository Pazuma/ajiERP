import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ChinaInputTaxDeductionBatch(Document):
	def validate(self):
		old = self.get_doc_before_save()
		if old and old.status != self.status:
			frappe.throw(_("抵扣批次状态只能通过税务服务变更"))
		if self.status != "Draft" and self.has_value_changed("items"):
			frappe.throw(_("非草稿抵扣批次不能修改税票明细"))
		self.invoice_count = len(self.items)
		self.net_amount = sum(flt(row.net_amount, 2) for row in self.items)
		self.tax_amount = sum(flt(row.tax_amount, 2) for row in self.items)
		self.gross_amount = sum(flt(row.gross_amount, 2) for row in self.items)
