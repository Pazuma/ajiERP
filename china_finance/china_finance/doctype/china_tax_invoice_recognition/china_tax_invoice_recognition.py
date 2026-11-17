import frappe
from frappe import _
from frappe.model.document import Document

from china_finance.services.archive import calculate_file_hash


class ChinaTaxInvoiceRecognition(Document):
	def validate(self):
		if self.is_new() and self.status not in (None, "Draft") and not self.flags.allow_recognition_result_insert:
			frappe.throw(_("新识别任务必须从 Draft 状态开始"))
		if self.source_file:
			self.file_hash = calculate_file_hash(self.source_file)
		if self.tax_invoice and self.status != "Converted":
			frappe.throw(_("已关联税务发票的识别任务必须为 Converted 状态"))
