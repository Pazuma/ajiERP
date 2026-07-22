import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from china_finance.services.disclosure import get_effective_policies


class ChinaFinancialStatementNotes(Document):
	def before_validate(self):
		if self.company and self.from_date and self.to_date and self.version:
			self.notes_key = "|".join((self.company, str(self.from_date), str(self.to_date), str(self.version)))

	def validate(self):
		if self.from_date > self.to_date:
			frappe.throw(_("报告期起始日期不能晚于截止日期"))
		standard = frappe.db.get_value("China Finance Settings", self.company, "accounting_standard")
		if standard and standard != self.accounting_standard:
			frappe.throw(_("附注采用的准则必须与公司中国财务设置一致"))

	def before_submit(self):
		frappe.only_for(("System Manager", "China Finance Manager"))
		policies = get_effective_policies(self.company, self.to_date)
		if not policies:
			frappe.throw(_("提交财务报表附注前必须先提交生效的会计政策"))
		self.policies_json = json.dumps(policies, ensure_ascii=False, sort_keys=True, default=str)
		from china_finance.services.financial_statement import build_statement

		statements = {
			statement_type: build_statement(self.company, statement_type, self.from_date, self.to_date)
			for statement_type in ("Balance Sheet", "Profit and Loss", "Cash Flow", "Changes in Equity")
		}
		important_codes = {
			"Balance Sheet": ("TOTAL_ASSETS", "TOTAL_LIABILITIES", "OWNERS_EQUITY"),
			"Profit and Loss": ("OPERATING_REVENUE", "TOTAL_PROFIT", "NET_PROFIT"),
			"Cash Flow": ("OPERATING_CASH_FLOW", "INVESTING_CASH_FLOW", "FINANCING_CASH_FLOW", "NET_CASH_INCREASE"),
			"Changes in Equity": ("OPENING_EQUITY", "NET_PROFIT", "CLOSING_EQUITY"),
		}
		payload = {}
		for statement_type, result in statements.items():
			values = {row["row_code"]: row["amount"] for row in result["rows"]}
			payload[statement_type] = {code: values.get(code, 0) for code in important_codes[statement_type]}
		payload["cash_flow_supplement"] = statements["Cash Flow"].get("cash_flow_supplement", [])
		payload["cash_equivalent_composition"] = statements["Cash Flow"].get("cash_equivalent_composition", [])
		self.statement_data_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def before_cancel(self):
		frappe.only_for(("System Manager", "China Finance Manager"))
