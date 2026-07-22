import frappe
from frappe import _
from frappe.model.document import Document

from china_finance.services.sales_settlement import (
	create_receivable_for_settlement,
	validate_sales_settlement,
	validate_settlement_confirmation,
)


class ChinaSalesSettlement(Document):
	def validate(self):
		validate_sales_settlement(self)

	def before_submit(self):
		if self.status not in ("草稿", "待客户确认", "待内部复核"):
			frappe.throw(_("当前状态的销售结算单不可提交"))
		validate_settlement_confirmation(self)
		create_receivable_for_settlement(self)

	def before_cancel(self):
		if self.status == "已生成应收":
			frappe.throw(_("已生成正式应收的结算单不可取消，请通过销售退货或贷项销售发票更正"))
		self.status = "已取消"
		self.cancellation_reason = self.cancellation_reason or _("手工取消")
		self.flags.ignore_settlement_state = True
