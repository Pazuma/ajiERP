import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ChinaReconciliationDifference(Document):
	def before_validate(self):
		if self.statement:
			statement = frappe.get_cached_doc("China Reconciliation Statement", self.statement)
			self.company = statement.company
			self.scope = statement.scope

	def validate(self):
		old = self.get_doc_before_save()
		if old and old.status != self.status:
			frappe.throw(_("对账差异状态只能通过差异处理服务变更"))
		if self.source_name and not self.source_doctype:
			frappe.throw(_("选择来源单据时必须填写来源单据类型"))
		if not flt(self.amount):
			frappe.throw(_("差异金额不能为零"))
