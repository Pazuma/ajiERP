import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


KPI_TARGET_DEFINITIONS = {
	"collection_amount_monthly": {"name": "月度回款金额", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"production_completion_rate": {"name": "生产完工率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"purchase_on_time_rate": {"name": "采购到货及时率", "period_type": "Monthly", "evaluation_direction": "Higher Is Better"},
	"realtime_inventory_amount": {"name": "实时库存总金额", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"safety_stock_warning_count": {"name": "安全库存预警物料数量", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"purchase_in_transit_amount": {"name": "采购在途金额", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
	"material_over_consumption_rate": {"name": "生产领料超耗率", "period_type": "Monthly", "evaluation_direction": "Lower Is Better"},
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
