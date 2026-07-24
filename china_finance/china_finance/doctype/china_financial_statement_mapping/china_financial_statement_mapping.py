import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ChinaFinancialStatementMapping(Document):
	REVIEW_RELEVANT_FIELDS = (
		"company", "template", "row_code", "account", "cash_inflow_row_code", "cash_outflow_row_code",
		"sign_multiplier", "effective_from", "effective_to", "account_number_snapshot", "mapping_basis",
	)

	def before_validate(self):
		if self.company and self.template and self.account and self.effective_from:
			self.mapping_key = "|".join((self.company, self.template, self.account, str(self.effective_from)))
		if self.account:
			self.account_number_snapshot = frappe.db.get_value("Account", self.account, "account_number")
		if self.mapping_source == "Manual":
			self.mapping_basis = "Manual"

	def validate(self):
		if self.account:
			account = frappe.db.get_value("Account", self.account, ["company", "is_group"], as_dict=True)
			if account.company != self.company:
				frappe.throw(_("映射科目必须属于所选公司"))
			if account.is_group:
				frappe.throw(_("财务报表科目映射只能选择末级会计科目，不能选择父科目"))
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		self.validate_no_overlapping_period()
		if self.template and self.row_code:
			template = frappe.get_cached_doc("China Financial Statement Template", self.template)
			if (
				template.statement_type == "Profit and Loss"
				and self.account_number_snapshot == "6901"
			):
				frappe.throw(_("6901 以前年度损益调整不得计入当期利润表，请使用前期差错更正记录进行严格追溯调整"))
			rows_by_code = {row.row_code: row for row in template.rows}
			if self.row_code not in rows_by_code:
				frappe.throw(_("模板中不存在报表行 {0}").format(self.row_code))
			if rows_by_code[self.row_code].row_type != "Mapped Accounts":
				frappe.throw(_("科目只能映射到明细项目，不能映射到标题或公式行"))
		self.invalidate_review_when_mapping_changes()
		if self.reviewed and not self.reviewed_by:
			self.reviewed_by = frappe.session.user
			self.reviewed_on = now_datetime()
		if self.template:
			template = frappe.get_cached_doc("China Financial Statement Template", self.template)
			valid_codes = {row.row_code for row in template.rows}
			for fieldname in ("row_code", "cash_inflow_row_code", "cash_outflow_row_code"):
				value = self.get(fieldname)
				if value and value not in valid_codes:
					frappe.throw(_("{0} 不是模板 {1} 的有效行编码").format(self.meta.get_label(fieldname), self.template))
			if template.statement_type == "Cash Flow" and not (
				self.cash_inflow_row_code and self.cash_outflow_row_code
			):
				frappe.throw(_("现金流量表映射必须同时配置现金流入行和现金流出行"))

	def validate_no_overlapping_period(self):
		if not (self.company and self.template and self.account and self.effective_from):
			return
		this_end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		for row in frappe.get_all(
			"China Financial Statement Mapping",
			filters={
				"company": self.company, "template": self.template, "account": self.account,
				"name": ["!=", self.name or ""],
			}, fields=["name", "effective_from", "effective_to"],
		):
			other_end = getdate(row.effective_to) if row.effective_to else getdate("9999-12-31")
			if getdate(self.effective_from) <= other_end and getdate(row.effective_from) <= this_end:
				frappe.throw(_("该科目在当前模板中的映射有效期间与 {0} 重叠").format(row.name))

	def invalidate_review_when_mapping_changes(self):
		if self.is_new() or not self.reviewed:
			return
		previous = self.get_doc_before_save()
		if not previous:
			return
		if any(self.get(fieldname) != previous.get(fieldname) for fieldname in self.REVIEW_RELEVANT_FIELDS):
			self.reviewed = 0
			self.reviewed_by = None
			self.reviewed_on = None
			self.review_notes = None
