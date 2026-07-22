import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ChinaCashEquivalentScope(Document):
	REVIEW_FIELDS = (
		"company", "account", "classification", "included", "restricted",
		"restriction_reason", "policy_basis", "effective_from", "effective_to",
	)

	def before_validate(self):
		if self.company and self.account and self.effective_from:
			self.scope_key = "|".join((self.company, self.account, str(self.effective_from)))
		if self.classification == "排除项":
			self.included = 0

	def validate(self):
		if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
			frappe.throw(_("失效日期不能早于生效日期"))
		account = frappe.db.get_value(
			"Account", self.account, ["company", "is_group", "account_type"], as_dict=True
		)
		if not account or account.company != self.company:
			frappe.throw(_("现金范围科目必须属于所选公司"))
		if account.is_group:
			frappe.throw(_("现金范围只能选择末级科目"))
		if self.included and account.account_type not in {"Cash", "Bank"}:
			frappe.throw(_("纳入现金及现金等价物的科目必须是现金或银行科目"))
		if self.restricted and not self.restriction_reason:
			frappe.throw(_("受限资金必须填写受限原因"))
		self._validate_no_overlap()
		self._invalidate_review()

	def _validate_no_overlap(self):
		for row in frappe.get_all(
			"China Cash Equivalent Scope",
			filters={"company": self.company, "account": self.account, "name": ["!=", self.name or ""]},
			fields=["name", "effective_from", "effective_to"],
		):
			other_end = getdate(row.effective_to) if row.effective_to else getdate("9999-12-31")
			this_end = getdate(self.effective_to) if self.effective_to else getdate("9999-12-31")
			if getdate(self.effective_from) <= other_end and getdate(row.effective_from) <= this_end:
				frappe.throw(_("科目 {0} 的现金范围有效期间与 {1} 重叠").format(self.account, row.name))

	def _invalidate_review(self):
		if self.is_new() or not self.reviewed:
			return
		previous = self.get_doc_before_save()
		if previous and any(self.get(field) != previous.get(field) for field in self.REVIEW_FIELDS):
			self.reviewed = 0
			self.reviewed_by = None
			self.reviewed_on = None
			self.review_notes = None

	@frappe.whitelist()
	def mark_reviewed(self, notes=None):
		self.check_permission("write")
		self.reviewed = 1
		self.reviewed_by = frappe.session.user
		self.reviewed_on = now_datetime()
		self.review_notes = notes
		self.save()
		return self.name
