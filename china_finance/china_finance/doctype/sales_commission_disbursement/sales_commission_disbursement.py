import frappe
from frappe.model.document import Document


class SalesCommissionDisbursement(Document):

	def validate(self):
		from china_finance.services.sales_commission_payments import validate_ledger
		validate_ledger(self)

	def on_trash(self):
		frappe.throw("提成记录不允许删除，请保留历史并使用修订、追回或作废操作。")

