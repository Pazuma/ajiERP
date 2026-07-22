import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ChinaTaxAccountMapping(Document):
	def before_validate(self):
		if self.company and self.direction and self.account and self.effective_from:
			self.mapping_key = "|".join((self.company, self.direction, self.account, str(self.effective_from)))

	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		if self.account:
			account = frappe.db.get_value("Account", self.account, ["company", "is_group", "account_type"], as_dict=True)
			if not account or account.company != self.company:
				frappe.throw(_("税务科目必须属于所选公司"))
			if account.is_group:
				frappe.throw(_("税务科目映射必须选择末级科目"))
			if account.account_type != "Tax":
				frappe.throw(_("税务科目的科目类型必须为 Tax"))
		self.validate_no_overlapping_period()

	def validate_no_overlapping_period(self):
		if not (self.company and self.direction and self.account and self.effective_from):
			return
		this_end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
		for row in frappe.get_all(
			"China Tax Account Mapping",
			filters={"company": self.company, "direction": self.direction, "account": self.account, "name": ["!=", self.name or ""]},
			fields=["name", "effective_from", "effective_to"],
		):
			other_end = getdate(row.effective_to) if row.effective_to else getdate("9999-12-31")
			if getdate(self.effective_from) <= other_end and getdate(row.effective_from) <= this_end:
				frappe.throw(_("该税务科目的有效期间与 {0} 重叠").format(row.name))
