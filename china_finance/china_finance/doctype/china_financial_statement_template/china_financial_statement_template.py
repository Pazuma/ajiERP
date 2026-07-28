import re

import frappe
from frappe import _
from frappe.model.document import Document


class ChinaFinancialStatementTemplate(Document):
	def before_validate(self):
		if self.accounting_standard and self.statement_type and self.version:
			self.template_key = "|".join((self.accounting_standard, self.statement_type, self.version))
		for index, row in enumerate(self.rows):
			if row.is_child and index == 0:
				frappe.throw(_("首个报表项目不能设为子行"))
			# ``is_child`` controls whether a row participates in the hierarchy;
			# ``indent`` carries its actual depth.  Do not collapse all descendants
			# to one level when a statutory template is saved.
			row.indent = max(int(row.indent or 0), 1) if row.is_child else 0

	def validate(self):
		codes = [row.row_code for row in self.rows]
		if len(codes) != len(set(codes)):
			frappe.throw(_("报表行编码不能重复"))
		valid_codes = set(codes)
		for row in self.rows:
			if not re.match(r"^[A-Z][A-Z0-9_]*$", row.row_code or ""):
				frappe.throw(_("行编码只能使用大写字母、数字和下划线：{0}").format(row.row_code))
			if row.row_type == "Formula":
				from china_finance.services.financial_statement import validate_formula

				validate_formula(row.formula, valid_codes)
		from china_finance.services.financial_statement import validate_formula_graph

		validate_formula_graph(self.rows)
