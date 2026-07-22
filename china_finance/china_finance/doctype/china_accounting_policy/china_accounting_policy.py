import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now_datetime


class ChinaAccountingPolicy(Document):
	def before_validate(self):
		if self.company and self.category and self.version:
			self.policy_key = "|".join((self.company, self.category, self.version))

	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		standard = frappe.db.get_value("China Finance Settings", self.company, "accounting_standard")
		if standard and standard != self.accounting_standard:
			frappe.throw(_("会计政策采用的准则必须与公司中国财务设置一致"))
		if self.change_type != "首次制定" and not self.previous_policy:
			frappe.throw(_("政策变更必须关联上一版本政策"))
		if self.change_type != "首次制定" and not self.change_reason:
			frappe.throw(_("政策变更必须填写变更原因"))

	def before_submit(self):
		frappe.only_for(("System Manager", "China Finance Manager"))
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def on_submit(self):
		if self.previous_policy:
			previous = frappe.get_doc("China Accounting Policy", self.previous_policy)
			if previous.company != self.company or previous.category != self.category or previous.docstatus != 1:
				frappe.throw(_("上一版本政策必须是同一公司、同一类别的已提交政策"))
			if not previous.effective_to or getdate(previous.effective_to) >= getdate(self.effective_from):
				previous.db_set("effective_to", add_days(self.effective_from, -1))

	def before_cancel(self):
		frappe.only_for(("System Manager", "China Finance Manager"))

