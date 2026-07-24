import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


APPROVERS = ("System Manager", "China Finance Manager")


class ChinaPriorPeriodErrorAdjustment(Document):
	def before_validate(self):
		if self.company and self.journal_entry and self.prior_period_end:
			self.adjustment_key = "|".join((self.company, self.journal_entry, str(self.prior_period_end)))
		if self.is_new() and not self.status:
			self.status = "草稿"

	def validate(self):
		journal = frappe.get_doc("Journal Entry", self.journal_entry)
		if journal.docstatus != 1 or journal.company != self.company:
			frappe.throw(_("追溯调整日记账必须为本公司已提交单据"))
		if getdate(journal.posting_date) <= getdate(self.prior_period_end):
			frappe.throw(_("追溯调整日记账日期必须晚于原错报期间截止日"))
		accounts = [row.account for row in journal.accounts]
		if any(frappe.db.get_value("Account", account, "account_number") == "6901" for account in accounts):
			frappe.throw(_("严格追溯调整不得使用 6901 以前年度损益调整科目"))
		retained = frappe.db.get_value("China Finance Settings", self.company, "retained_earnings_account")
		if retained not in accounts:
			frappe.throw(_("追溯调整日记账必须直接使用配置的未分配利润科目"))
		invalid_accounts = [
			account for account in accounts
			if account != retained and frappe.db.get_value("Account", account, "root_type") not in {"Asset", "Liability"}
		]
		if invalid_accounts:
			frappe.throw(
				_("严格追溯调整除未分配利润外，只能直接调整资产或负债科目：{0}").format(
					", ".join(invalid_accounts)
				)
			)
		from china_finance.services.prior_period_error import build_adjustment_lines

		self.set("lines", build_adjustment_lines(self.company, self.journal_entry, self.prior_period_end))

	def before_submit(self):
		frappe.only_for(APPROVERS)
		if not self.evidence_file or not self.lines:
			frappe.throw(_("提交前必须上传依据并生成报表影响明细"))
		self.status = "已审批"
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def before_cancel(self):
		frappe.only_for(APPROVERS)
		self.status = "已取消"
