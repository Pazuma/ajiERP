import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime

from china_finance.services.archive import create_archive_record
from china_finance.services.purchase_reconciliation import (
	STATUS_BLOCKED,
	STATUS_WAIVED,
	apply_purchase_reconciliation_statuses,
)


class ChinaReconciliationStatement(Document):
	def validate(self):
		if self.from_date > self.to_date:
			frappe.throw(_("起始日期不能晚于截止日期"))
		if self.statement_type in ("Customer", "Supplier"):
			self.party_type = self.statement_type
			if not self.party:
				frappe.throw(_("客户或供应商对账必须选择往来单位"))
			if self.statement_type == "Customer" and self.statement_basis == "Ledger":
				self._validate_customer_ledger_snapshot()
			elif self.statement_type == "Customer" and self.lines:
				for row in self.lines:
					if row.voucher_type and row.voucher_type != "Delivery Note":
						frappe.throw(_("客户对账明细必须来自送货单"))
					if not row.voucher_no:
						frappe.throw(_("客户对账明细缺少来源送货单"))
					source = frappe.db.get_value(
						"Delivery Note", row.voucher_no,
						["company", "customer", "posting_date", "docstatus", "currency"], as_dict=True,
					)
					if not source or source.docstatus != 1:
						frappe.throw(_("送货单 {0} 不存在或未提交").format(row.voucher_no))
					if frappe.db.get_value("Delivery Note", row.voucher_no, "custom_china_settlement_mode") != "对账结算后确认应收":
						frappe.throw(_("送货单 {0} 未启用对账结算模式").format(row.voucher_no))
					if source.company != self.company or source.customer != self.party:
						frappe.throw(_("送货单 {0} 与对账单公司或客户不一致").format(row.voucher_no))
					if not (getdate(self.from_date) <= getdate(source.posting_date) <= getdate(self.to_date)):
						frappe.throw(_("送货单 {0} 不在对账期间内").format(row.voucher_no))
					if self.currency and source.currency != self.currency:
						frappe.throw(_("送货单 {0} 的币种与对账单不一致").format(row.voucher_no))
					if not row.source_detail_name:
						frappe.throw(_("送货单 {0} 的对账明细缺少来源行").format(row.voucher_no))
					source_row = frappe.db.get_value(
						"Delivery Note Item", row.source_detail_name,
						["parent", "item_code", "qty", "rate", "amount"], as_dict=True,
					)
					if not source_row or source_row.parent != row.voucher_no:
						frappe.throw(_("送货单 {0} 的来源明细已不存在").format(row.voucher_no))
					if source_row.item_code != row.item_code or any(
						abs(flt(source_row.get(field)) - flt(row.get(field))) > 0.000001
						for field in ("qty", "rate", "amount")
					):
						frappe.throw(_("送货单 {0} 的明细已变化，请重新加载对账数据").format(row.voucher_no))
		elif not self.bank_account or not self.account:
			frappe.throw(_("银行对账必须选择银行账户及其会计科目"))
		if self.scope:
			scope = frappe.get_cached_doc("China Reconciliation Scope", self.scope)
			if scope.company != self.company or scope.scope_type != self.statement_type:
				frappe.throw(_("对账单与对账范围不一致"))
			self.confirmation_method = scope.confirmation_method
			duplicate = frappe.db.exists(
				"China Reconciliation Statement",
				{
					"scope": self.scope, "from_date": self.from_date, "to_date": self.to_date,
					"status": ["!=", "Superseded"], "name": ["!=", self.name or ""],
				},
			)
			if duplicate:
				frappe.throw(_("该对账范围和期间已存在有效对账单：{0}").format(duplicate))
		self.period_key = f"{self.from_date}|{self.to_date}"
		if self.statement_type == "Supplier":
			apply_purchase_reconciliation_statuses(self.lines)
			self.blocked_line_count = sum(row.reconciliation_status == STATUS_BLOCKED for row in self.lines)
			self.waived_line_count = sum(row.reconciliation_status == STATUS_WAIVED for row in self.lines)
			for row in self.lines:
				if row.reconciliation_status == STATUS_WAIVED:
					if not row.waiver_reason or not row.waived_by or not row.waived_on:
						frappe.throw(_("采购齐套豁免必须记录原因、豁免人和豁免时间"))
					if not set(("System Manager", "Accounts Manager", "China Finance Manager")) & set(frappe.get_roles()):
						frappe.throw(_("只有财务经理可以豁免采购齐套校验"))
		comparison_balance = self.calculated_bank_balance if self.statement_type == "Bank" else self.closing_balance
		self.difference = flt(self.counterparty_balance) - flt(comparison_balance)

	def _validate_customer_ledger_snapshot(self):
		from china_finance.services.customer_reconciliation_statement import get_customer_ledger_snapshot

		if not self.snapshot_key:
			frappe.throw(_("请先加载客户往来账"))
		snapshot = get_customer_ledger_snapshot(self.company, self.party, self.from_date, self.to_date)
		if snapshot["snapshot_key"] != self.snapshot_key:
			frappe.throw(_("客户账务数据已变化，请重新加载往来账"))
		expected = {row["gl_entry"]: row for row in snapshot["rows"]}
		if len(self.lines) != len(expected) or any(not row.gl_entry or row.gl_entry not in expected for row in self.lines):
			frappe.throw(_("客户往来账明细不完整，请重新加载"))
		for row in self.lines:
			source = expected[row.gl_entry]
			if (
				row.voucher_type != source["voucher_type"]
				or row.voucher_no != source["voucher_no"]
				or row.account != source["account"]
				or any(abs(flt(row.get(field)) - flt(source[field])) > 0.000001 for field in ("debit", "credit", "balance"))
			):
				frappe.throw(_("客户往来账明细已被修改，请重新加载"))
		expected_opening = {row["sales_invoice"]: row for row in snapshot.get("opening_documents", [])}
		# 兼容尚未 migrate 的旧站点：新增子表字段不存在时不阻断原有对账单保存。
		opening_rows = getattr(self, "opening_documents", None)
		if opening_rows is not None and len(opening_rows) != len(expected_opening):
			frappe.throw(_("期初未结账单明细不完整，请重新加载"))
		for row in opening_rows or []:
			source = expected_opening.get(row.sales_invoice)
			if not source or any(
				abs(flt(row.get(field)) - flt(source.get(field))) > 0.000001
				for field in ("original_amount", "settled_amount", "outstanding_amount")
			):
				frappe.throw(_("期初账单明细已被修改，请重新加载"))
		order_rows = getattr(self, "order_billing_rows", None)
		if order_rows is not None and len(order_rows) != len(snapshot.get("order_billing_rows", [])):
			frappe.throw(_("订单账单明细不完整，请重新加载"))
		self.currency = snapshot["currency"]
		self.opening_balance = snapshot["opening_balance"]
		self.opening_document_count = snapshot.get("opening_document_count", 0)
		self.opening_document_total = snapshot.get("opening_document_total", 0)
		self.opening_adjustment = snapshot.get("opening_adjustment", 0)
		self.period_debit = snapshot["period_debit"]
		self.period_credit = snapshot["period_credit"]
		self.period_balance = snapshot["period_balance"]
		self.closing_balance = snapshot["closing_balance"]
		self.order_billing_count = snapshot.get("order_billing_count", 0)

	def before_submit(self):
		if self.statement_type == "Supplier" and self.blocked_line_count:
			blocked = [row.voucher_no for row in self.lines if row.reconciliation_status == STATUS_BLOCKED]
			frappe.throw(_("存在未齐套的采购发票，不能确认对账单：{0}").format("，".join(blocked)))
		if self.confirmation_method in ("External Confirmation", "Bank Statement") and not self.confirmation_file:
			frappe.throw(_("外部确认或银行对账必须上传确认附件"))
		if self.confirmation_method == "Internal Review":
			if not self.internal_review_reason:
				frappe.throw(_("内部复核必须填写原因"))
			if not set(("System Manager", "Accounts Manager", "China Finance Manager")) & set(frappe.get_roles()):
				frappe.throw(_("只有中国财务管理员可以确认内部复核"))
		if self.statement_type == "Bank" and not self.bank_snapshot_json:
			frappe.throw(_("银行对账必须先生成银行对账快照"))
		tolerance = flt(
			frappe.db.get_value("China Reconciliation Scope", self.scope, "amount_tolerance")
			if self.scope else frappe.db.get_value("China Finance Settings", self.company, "reconciliation_tolerance") or 0.01
		)
		if abs(flt(self.difference)) > tolerance:
			difference_total = frappe.db.sql(
				"SELECT COALESCE(SUM(amount), 0) FROM `tabChina Reconciliation Difference` WHERE statement=%s",
				(self.name,),
			)[0][0]
			if abs(flt(difference_total) - flt(self.difference)) > tolerance:
				frappe.throw(_("对账差异必须登记差异事项，且差异事项金额合计应等于对账差异"))
		self.status = "Confirmed"
		self.confirmed_by = frappe.session.user
		self.confirmed_on = now_datetime()

	def on_submit(self):
		if self.confirmation_file:
			create_archive_record(self.company, self.doctype, self.name, "Reconciliation", self.confirmation_file)
		if self.replaces:
			self._check_replacement_links()
			frappe.db.set_value("China Reconciliation Statement", self.replaces, "status", "Superseded", update_modified=False)
		if self.statement_type == "Customer" and self.statement_basis == "Delivery":
			from china_finance.services.sales_settlement import ensure_initial_settlement_from_reconciliation

			result = ensure_initial_settlement_from_reconciliation(self.name)
			if not result.get("name"):
				frappe.msgprint(_("对账已确认，但没有剩余可结算明细，未创建销售结算单"))
		elif self.statement_type == "Supplier":
			from china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up import ensure_purchase_follow_up_from_statement

			result = ensure_purchase_follow_up_from_statement(self)
			if not result.get("name"):
				frappe.msgprint(_("对账已确认，但未生成采购对账草稿：{0}").format(result["reason"]))

	def _check_replacement_links(self):
		if frappe.db.exists("China Sales Settlement", {"reconciliation_statement": self.replaces, "docstatus": 1}):
			frappe.throw(_("原对账单已有已提交销售结算单，不能替代"))
		if frappe.db.exists("Purchase Follow Up", {"reconciliation_statement": self.replaces, "docstatus": 1}):
			frappe.throw(_("原对账单已有已提交采购对账单，不能替代"))

	def before_cancel(self):
		if frappe.db.exists("China Sales Settlement", {"reconciliation_statement": self.name, "docstatus": 1}):
			frappe.throw(_("已有已提交的销售结算单，不能取消来源对账单"))
		if frappe.db.exists("Purchase Follow Up", {"reconciliation_statement": self.name, "docstatus": 1}):
			frappe.throw(_("已有已提交的采购对账单，不能取消来源对账单"))
