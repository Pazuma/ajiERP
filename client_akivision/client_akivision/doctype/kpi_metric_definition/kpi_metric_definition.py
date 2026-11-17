import re

import frappe
from frappe import _
from frappe.model.document import Document


METRIC_CODE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
VALID_DATATYPES = {"Int", "Float", "Currency", "Percent", "Date"}
VALID_PERIODS = {"Monthly", "Quarterly", "Yearly", "Custom"}
VALID_DIRECTIONS = {"Higher Is Better", "Lower Is Better", "Informational"}


class KPIMetricDefinition(Document):
	def validate(self):
		if not METRIC_CODE_RE.fullmatch(self.metric_code or ""):
			frappe.throw(_("指标编码必须使用英文 snake_case 格式。"))
		if self.datatype not in VALID_DATATYPES:
			frappe.throw(_("请选择有效的数据类型。"))
		if self.default_period_type not in VALID_PERIODS:
			frappe.throw(_("请选择有效的默认周期。"))
		if self.evaluation_direction not in VALID_DIRECTIONS:
			frappe.throw(_("请选择有效的评价方向。"))
		if self.is_compliance and self.evaluation_direction == "Informational":
			frappe.throw(_("合规指标必须配置目标评价方向。"))
		if self.drilldown_report and not frappe.db.exists("Report", self.drilldown_report):
			frappe.throw(_("下钻报表不存在：{0}").format(self.drilldown_report))
		try:
			version = int(self.definition_version or 0)
		except (TypeError, ValueError):
			version = 0
		if version < 1:
			frappe.throw(_("口径版本必须是大于等于 1 的整数。"))
