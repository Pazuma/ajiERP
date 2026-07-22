import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ChinaTaxInvoiceRequest(Document):
	def validate(self):
		old = self.get_doc_before_save()
		if old and old.status != self.status:
			frappe.throw(_("开票申请状态只能通过审批服务变更"))
		if self.status != "Draft" and self.has_value_changed("items"):
			frappe.throw(_("非草稿开票申请不能修改明细"))
		self.net_amount = self.tax_amount = 0
		for row in self.items:
			row.gross_amount = flt(row.net_amount, 2) + flt(row.tax_amount, 2)
			self.net_amount += flt(row.net_amount, 2)
			self.tax_amount += flt(row.tax_amount, 2)
		self.gross_amount = self.net_amount + self.tax_amount
		if self.request_type == "Red" and (not self.original_invoice or not self.credit_note):
			frappe.throw(_("红冲申请必须关联原蓝票和已提交销售退货或贷项发票"))
