import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


KPI_TARGET_DEFINITIONS = {
	"total_orders": {"name": "总订单数", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"total_sales_amount": {"name": "总销售额", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"collection_amount_monthly": {"name": "月度回款金额", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"received_amount": {"name": "已收款总额", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"receivable_amount": {"name": "应收款余额", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"settled_documents": {"name": "已结清单据数", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"unsettled_documents": {"name": "未结清单据数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"average_receivable_days": {"name": "平均应收天数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"overdue_over_90": {"name": "超90天逾期应收", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"receivable_turnover_days": {"name": "应收款周转天数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"completed_orders": {"name": "整单已完成订单数", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"pending_orders": {"name": "整单未完成订单数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"delivered_orders": {"name": "已交货订单数", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"delivering_orders": {"name": "交货中订单数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"undelivered_orders": {"name": "未交货订单数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"production_completion_rate": {"name": "生产完工率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"purchase_on_time_rate": {"name": "采购到货及时率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"realtime_inventory_amount": {"name": "实时库存总金额", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"safety_stock_warning_count": {"name": "安全库存预警物料数量", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"purchase_in_transit_amount": {"name": "采购在途金额", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"material_over_consumption_rate": {"name": "生产领料超耗率", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"salesperson_delivery_count": {"name": "业务员送货条数", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"salesperson_delivery_amount": {"name": "业务员送货金额", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"salesperson_received_amount": {"name": "业务员已回款", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"salesperson_receivable_amount": {"name": "业务员应收款", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"salesperson_delivery_rate": {"name": "业务员交付率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"salesperson_collection_rate": {"name": "业务员回款率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"prior_sales_amount": {"name": "上年同期销售额", "period_type": "Yearly", "evaluation_direction": "Informational"},
	"sales_growth_rate": {"name": "销售同比增长率", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"receivable_growth_rate": {"name": "应收同比增长率", "period_type": "Yearly", "evaluation_direction": "Lower Is Better"},
	"unfinished_orders": {"name": "未完成订单数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"status_mismatch_count": {"name": "状态不一致条数", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"high_tech_revenue": {"name": "高新收入总额", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"total_revenue": {"name": "总营收", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"high_tech_ratio": {"name": "高新收入占比", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"rd_project_count": {"name": "研发项目数量", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"rd_expense_amount": {"name": "研发费用金额", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
	"rd_expense_ratio": {"name": "研发费用占比", "period_type": "Yearly", "evaluation_direction": "Higher Is Better"},
}


class KPITarget(Document):
	def validate(self):
		definition = KPI_TARGET_DEFINITIONS.get(self.kpi_code)
		if not definition:
			frappe.throw(_("请选择看板支持的指标编码。"))
		self.kpi_name = definition["name"]
		if self.period_type == "Monthly" and self.period_value:
			try:
				getdate(f"{self.period_value}-01")
			except (TypeError, ValueError):
				frappe.throw(_("月度周期请使用 YYYY-MM 格式。"))
		duplicate = frappe.db.exists(
			"KPI Target",
			{
				"company": self.company,
				"kpi_code": self.kpi_code,
				"period_type": self.period_type,
				"period_value": self.period_value,
				"name": ["!=", self.name or ""],
			},
		)
		if duplicate:
			frappe.throw(_("该公司、指标和周期的目标值已存在。"))
