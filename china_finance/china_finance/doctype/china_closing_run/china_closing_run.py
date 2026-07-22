import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from china_finance.services.closing import create_report_snapshots, run_closing_checks


class ChinaClosingRun(Document):
	def validate(self):
		if self.from_date > self.to_date:
			frappe.throw(_("起始日期不能晚于截止日期"))
		if self.period_closing_voucher:
			company, posting_date, docstatus = frappe.db.get_value(
				"Period Closing Voucher", self.period_closing_voucher, ["company", "posting_date", "docstatus"]
			)
			if company != self.company or posting_date != self.to_date or docstatus != 1:
				frappe.throw(_("损益结转凭证必须已提交，且公司和截止日期与结账运行单一致"))

	def before_submit(self):
		checks = run_closing_checks(
			self.company, self.from_date, self.to_date, self.period_closing_voucher, self.closing_type
		)
		self.set("checks", checks)
		failed = [row["description"] for row in checks if row["severity"] == "Blocking" and not row["passed"]]
		if failed:
			frappe.throw(_("以下结账检查未通过：{0}").format("；".join(failed)))
		self.previous_frozen_date = frappe.db.get_value("Company", self.company, "accounts_frozen_till_date")
		self.status = "Closed"
		self.closed_by = frappe.session.user
		self.closed_on = now_datetime()

	def on_submit(self):
		create_report_snapshots(self)
		settings = frappe.get_cached_doc("China Finance Settings", self.company)
		if settings.freeze_on_close:
			frappe.db.set_value("Company", self.company, "accounts_frozen_till_date", self.to_date)
