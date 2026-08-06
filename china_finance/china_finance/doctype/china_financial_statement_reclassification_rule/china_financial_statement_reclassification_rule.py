import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ChinaFinancialStatementReclassificationRule(Document):
	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		template = frappe.get_cached_doc("China Financial Statement Template", self.template)
		rows = {row.row_code: row for row in template.rows}
		for fieldname in ("source_row_code", "target_row_code"):
			code = self.get(fieldname)
			if code not in rows:
				frappe.throw(_("模板中不存在报表行 {0}").format(code))
			if rows[code].row_type != "Mapped Accounts":
				frappe.throw(_("重分类项目必须是明细项目"))
