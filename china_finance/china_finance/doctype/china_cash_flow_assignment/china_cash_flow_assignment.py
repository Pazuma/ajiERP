import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class ChinaCashFlowAssignment(Document):
	IMMUTABLE_SOURCE_FIELDS = (
		"company",
		"posting_date",
		"china_accounting_voucher",
		"source_doctype",
		"source_name",
		"revision",
		"assignment_key",
	)

	def before_insert(self):
		if not self.flags.from_cash_flow_assignment_service:
			frappe.throw(_("现金流量指定单不能手工新建，请从已提交的中国会计凭证生成"))
		if not self.revision:
			from china_finance.services.cash_flow_assignment import _next_revision

			self.revision = _next_revision(self.china_accounting_voucher)
		if not self.assignment_key:
			self.assignment_key = f"{self.china_accounting_voucher}|{int(self.revision)}"

	def validate(self):
		self.validate_source()
		old = self.get_doc_before_save()
		if old:
			for fieldname in self.IMMUTABLE_SOURCE_FIELDS:
				if self.has_value_changed(fieldname):
					frappe.throw(_("现金流量指定单的来源信息不能修改"))
		if old and old.status != self.status and not self.flags.ignore_cash_flow_assignment_status:
			frappe.throw(_("现金流量指定单状态只能通过指定服务变更"))
		# A draft becomes Confirmed in the same save operation. Only records that
		# were already locked before this save must reject item changes.
		if old and old.status != "Draft" and self.has_value_changed("items"):
			frappe.throw(_("已确认或已作废的现金流量指定单不能修改明细"))
		if self.status == "Draft":
			if not old or self.has_value_changed("items") or self.has_value_changed("remarks"):
				self.assigned_by = frappe.session.user
				self.assigned_on = now_datetime()
		for row in self.items:
			row.cash_amount = flt(row.cash_amount, 2)
			row.assigned_amount = flt(row.assigned_amount, 2)

	def validate_source(self):
		if not self.china_accounting_voucher:
			frappe.throw(_("现金流量指定单必须关联中国会计凭证"))
		voucher = frappe.get_doc("China Accounting Voucher", self.china_accounting_voucher)
		if voucher.docstatus != 1 or voucher.source_event != "Posting":
			frappe.throw(_("现金流量指定单只能关联已提交的过账中国会计凭证"))

		expected = {
			"company": voucher.company,
			"posting_date": getdate(voucher.posting_date),
			"source_doctype": voucher.source_doctype,
			"source_name": voucher.source_name,
		}
		actual = {
			"company": self.company,
			"posting_date": getdate(self.posting_date),
			"source_doctype": self.source_doctype,
			"source_name": self.source_name,
		}
		if actual != expected:
			frappe.throw(_("公司、记账日期及来源单据必须与关联的中国会计凭证一致"))
		if not frappe.db.get_value(
			self.source_doctype,
			{"name": self.source_name, "docstatus": 1},
			"name",
		):
			frappe.throw(_("来源单据不存在或尚未提交"))

	def before_submit(self):
		from china_finance.services.cash_flow_assignment import prepare_cash_flow_assignment_confirmation

		prepare_cash_flow_assignment_confirmation(self)

	def before_cancel(self):
		self.status = "Cancelled"
		self.cancelled_by = frappe.session.user
		self.cancelled_on = now_datetime()
		self.cancellation_reason = self.cancellation_reason or _("手工或来源单据作废")
		self.flags.ignore_cash_flow_assignment_status = True

	def on_submit(self):
		from china_finance.services.cash_flow_assignment import _sync_source_assignment_state

		_sync_source_assignment_state(self)

	def on_cancel(self):
		from china_finance.services.cash_flow_assignment import _sync_source_assignment_state

		_sync_source_assignment_state(self)
