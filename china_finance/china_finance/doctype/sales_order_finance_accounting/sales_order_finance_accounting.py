import frappe
from frappe.model.document import Document


class SalesOrderFinanceAccounting(Document):
	def validate(self):
		from china_finance.services.sales_order_finance_accounting import validate_accounting
		validate_accounting(self)

	def on_trash(self):
		if self.status != "草稿":
			frappe.throw("已确认核算及历史版本不可删除。")
