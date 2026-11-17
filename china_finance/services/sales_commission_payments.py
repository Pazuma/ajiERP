"""Auditable receipt allocations and payment records; no banking or GL writes."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from china_finance.services.sales_commission_permissions import SHEET, RECEIPT, PAYMENT, assert_access
from china_finance.services.sales_commission_sources import digest, invoice_sources, number, order_context

_CONFIRM = object()


def receipt_source(doc):
	order = order_context(doc.sales_order)
	if doc.source_type not in ("Payment Entry", "人工核实") or doc.direction not in ("收款", "退款"):
		frappe.throw(_("请选择有效回款来源和方向。"))
	if not (doc.source_reference or "").strip():
		frappe.throw(_("必须填写回款来源编号。"))
	if doc.source_type == "Payment Entry":
		if not doc.payment_entry:
			frappe.throw(_("请选择收付款凭据。"))
		pe = frappe.get_doc("Payment Entry", doc.payment_entry)
		if pe.docstatus != 1 or pe.company != order.company or pe.party_type != "Customer" or pe.party != order.customer:
			frappe.throw(_("收付款凭据须已提交，且公司与客户相符。"))
		expected = "Receive" if doc.direction == "收款" else "Pay"
		if pe.payment_type != expected:
			frappe.throw(_("回款方向与收付款凭据不符。"))
		factor = number(pe.source_exchange_rate if expected == "Receive" else pe.target_exchange_rate)
		if factor <= 0:
			frappe.throw(_("收付款汇率无效。"))
		references = [r for r in pe.references if (r.reference_doctype == "Sales Invoice" and r.reference_name == doc.sales_invoice)
			or (not doc.sales_invoice and r.reference_doctype == "Sales Order" and r.reference_name == order.name)]
		if not references:
			frappe.throw(_("凭据未明确分配到所选发票或订单，预收款须先核实归属。"))
		capacity = min(abs(flt(pe.base_paid_amount)), abs(flt(pe.base_received_amount)))
		reference_capacity = min(capacity, sum(abs(flt(r.allocated_amount)) * factor for r in references))
		key = "PE:" + pe.name
		snapshot = dict(name=pe.name, modified=str(pe.modified), status=pe.docstatus, capacity=capacity,
			references=[dict(type=r.reference_doctype, name=r.reference_name, amount=r.allocated_amount) for r in pe.references], factor=factor)
	else:
		if doc.payment_entry or not (doc.reason or "").strip() or not doc.evidence:
			frappe.throw(_("人工核实须填写原因、附件，且不能冒用自动收款凭据。"))
		capacity = reference_capacity = number(doc.verified_source_amount)
		if capacity <= 0:
			frappe.throw(_("请填写人工核实的凭据总金额。"))
		key = "MANUAL:" + doc.source_reference.strip() + ":" + doc.direction
		snapshot = dict(key=key, capacity=capacity)
	amount = number(doc.amount)
	if amount <= 0 or amount > capacity:
		frappe.throw(_("分配金额须大于零且不能超过凭据金额。"))
	net = 0
	if doc.sales_invoice:
		invoices = invoice_sources(order)
		invoice = next((r for r in invoices if r["name"] == doc.sales_invoice), None)
		is_refund = bool(invoice and invoice["is_return"])
		if not invoice or not invoice["gross"] or is_refund != (doc.direction == "退款"):
			frappe.throw(_("发票须有效关联本订单，且与收退款方向一致。"))
		if amount > abs(invoice["gross"]) + 0.005:
			frappe.throw(_("分配金额不能超过本订单的发票分摊额。"))
		net = amount * invoice["net"] / invoice["gross"]
		snapshot["invoice"] = invoice
	return dict(key=digest([order.company, key]), hash=digest(snapshot), capacity=capacity,
		reference_capacity=reference_capacity, net_amount=flt(net, order.precision("base_grand_total") or 2))


def validate_ledger(doc):
	assert_access(doc.sales_order, "finance")
	order = frappe.get_doc("Sales Order", doc.sales_order)
	if order.docstatus != 1 and not (doc.doctype == PAYMENT and doc.direction in ("追回", "冲销发放") and order.docstatus == 2):
		frappe.throw(_("非有效订单只能登记历史提成的追回或冲销。"))
	old = doc.get_doc_before_save()
	confirming = doc.flags.commission_confirm is _CONFIRM
	if old and old.status != "草稿":
		frappe.throw(_("已确认台账不可修改，请使用冲销或作废操作。"))
	if old and doc.sales_order != old.sales_order:
		frappe.throw(_("台账订单不可修改。"))
	if doc.status not in ("草稿", "已确认") or (doc.status == "已确认" and not confirming) or (doc.is_new() and doc.status != "草稿"):
		frappe.throw(_("请使用台账确认操作。"))
	doc.company, doc.customer = order.company, order.customer
	doc.company_currency = frappe.get_cached_value("Company", order.company, "default_currency")
	if number(doc.amount) <= 0:
		frappe.throw(_("金额必须大于零。"))
	doc.amount = flt(doc.amount, doc.precision("amount"))
	if doc.amount <= 0:
		frappe.throw(_("金额不能小于币种精度。"))
	if doc.doctype == RECEIPT:
		source = receipt_source(doc)
		doc.source_key, doc.source_hash, doc.net_amount = source["key"], source["hash"], source["net_amount"]
	else:
		if doc.direction not in ("发放", "追回", "冲销发放"):
			frappe.throw(_("请选择有效发放方向。"))
		sheet = frappe.get_doc(SHEET, doc.commission_sheet)
		if sheet.sales_order != doc.sales_order or not any(r.sales_person == doc.sales_person for r in sheet.sales_people):
			frappe.throw(_("提成版本或业务人员与订单不符。"))
		if not doc.payment_reference or not doc.evidence:
			frappe.throw(_("请填写实际支付/追回凭据编号并上传附件。"))
		if doc.direction == "冲销发放" and not doc.reversal_of:
			frappe.throw(_("冲销必须关联原发放记录。"))
		if doc.direction != "冲销发放" and doc.reversal_of:
			frappe.throw(_("只有冲销记录可以指定原发放记录。"))
	doc.confirmed_by = frappe.session.user if confirming else None
	doc.confirmed_on = now_datetime() if confirming else None
	doc.confirmed_date = doc.confirmed_on.date() if confirming else None
	# Unique per external business record. Revision/retry cannot create a duplicate.
	doc.idempotency_key = digest([doc.company, doc.doctype,
		doc.source_reference if doc.doctype == RECEIPT else doc.payment_reference,
		doc.sales_order, doc.get("sales_invoice"), doc.get("sales_person"), doc.direction]) if confirming else None


def paid_by_person(sales_order):
	result = {}
	for row in frappe.get_all(PAYMENT, filters={"sales_order": sales_order, "status": "已确认"}, fields=["sales_person", "amount", "direction"]):
		result[row.sales_person] = result.get(row.sales_person, 0) + flt(row.amount) * (1 if row.direction == "发放" else -1)
	return result


def release_rows(doc, check_source=True, internal=False):
	from china_finance.services.sales_commission import effective_state
	valid = doc.status == "已作废" or ((effective_state(doc, internal=internal) == "已确认") if check_source else doc.status == "已确认")
	paid = paid_by_person(doc.sales_order)
	if doc.release_condition == "确认后可发放":
		ratio = 1
	elif doc.release_condition == "全额回款后可发放":
		ratio = 1 if doc.receipt_amount + 0.005 >= doc.receivable_baseline > 0 else 0
	else:
		ratio = flt(doc.receipt_ratio)
	people = {r.sales_person: r for r in doc.sales_people}
	result = []
	for person in sorted(set(people) | set(paid)):
		row = people.get(person)
		earned = flt(row.commission_amount) if row and doc.status != "已作废" else 0
		eligible = flt(earned * ratio, doc.precision("commission_total")) if valid else None
		already = flt(paid.get(person))
		result.append(frappe._dict(sales_person=person, commission_amount=earned, eligible_amount=eligible, paid_amount=already,
			available_amount=max(flt(eligible) - already, 0) if valid else 0,
			unreleased_amount=max(earned - flt(eligible), 0) if valid else None,
			recoverable_amount=max(already - flt(eligible), 0) if valid else None,
			status=doc.status if doc.status == "已作废" else "已确认" if valid else "待复核"))
	return result


@frappe.whitelist()
def get_release_context(commission_sheet):
	doc = frappe.get_doc(SHEET, commission_sheet)
	assert_access(doc.sales_order)
	# Finance may consume release amounts without receiving the gross-margin base.
	from china_finance.services.sales_commission_permissions import can_margin
	if doc.basis_type == "财务确认毛利" and not can_margin():
		frappe.throw(_("请由具备毛利基数授权的财务核对。"), frappe.PermissionError)
	return release_rows(doc)


def _locked_ledger(name, doctype, modified):
	doc = frappe.get_doc(doctype, name)
	assert_access(doc.sales_order, "finance")
	# Consistent lock ordering for cross-order allocations of one source.
	frappe.db.sql("select name from `tabCompany` where name=%s for update", frappe.db.get_value("Sales Order", doc.sales_order, "company"))
	from china_finance.services.sales_commission import lock_order
	lock_order(doc.sales_order)
	doc.reload()
	if doc.status != "草稿" or str(doc.modified) != str(modified):
		frappe.throw(_("台账已修改，请刷新后重试。"), frappe.TimestampMismatchError)
	return doc


@frappe.whitelist(methods=["POST"])
def confirm_receipt_allocation(name, modified):
	doc = _locked_ledger(name, RECEIPT, modified)
	if doc.payment_entry:
		frappe.has_permission("Payment Entry", "read", doc=doc.payment_entry, throw=True)
		frappe.db.sql("select name from `tabPayment Entry` where name=%s for update", doc.payment_entry)
	source = receipt_source(doc)
	others = frappe.get_all(RECEIPT, filters={"source_key": source["key"], "status": "已确认"},
		fields=["amount", "sales_invoice", "source_hash", "verified_source_amount"])
	key = digest([doc.company, doc.doctype, doc.source_reference, doc.sales_order, doc.sales_invoice, None, doc.direction])
	if frappe.db.exists(RECEIPT, {"idempotency_key": key, "status": "已确认"}):
		frappe.throw(_("该回款来源已登记，请勿重复确认。"))
	if doc.source_type == "人工核实" and any(abs(flt(r.verified_source_amount) - source["capacity"]) > 0.005 for r in others):
		frappe.throw(_("同一人工凭据的核实总金额不一致。"))
	if sum(flt(r.amount) for r in others) + doc.amount > source["capacity"] + 0.005:
		frappe.throw(_("累计分配超过凭据有效金额。"))
	if sum(flt(r.amount) for r in others if r.sales_invoice == doc.sales_invoice) + doc.amount > source["reference_capacity"] + 0.005:
		frappe.throw(_("累计分配超过凭据该引用行金额。"))
	if doc.sales_invoice:
		inv = next(r for r in invoice_sources(order_context(doc.sales_order)) if r["name"] == doc.sales_invoice)
		allocated = frappe.get_all(RECEIPT, filters={"sales_order": doc.sales_order, "sales_invoice": doc.sales_invoice,
			"direction": doc.direction, "status": "已确认"}, pluck="amount")
		if sum(allocated) + doc.amount > abs(inv["gross"]) + 0.005:
			frappe.throw(_("本订单发票累计分配超额。"))
	doc.flags.commission_confirm, doc.status = _CONFIRM, "已确认"
	doc.save()
	return doc.name


@frappe.whitelist(methods=["POST"])
def void_receipt_allocation(name, reason):
	doc = frappe.get_doc(RECEIPT, name)
	assert_access(doc.sales_order, "finance")
	from china_finance.services.sales_commission import lock_order
	frappe.db.sql("select name from `tabCompany` where name=%s for update", doc.company)
	lock_order(doc.sales_order)
	doc.reload()
	if doc.status != "已确认" or not (reason or "").strip():
		frappe.throw(_("仅可作废已确认分配，且须说明原因；实际退款应另记退款分配。"))
	frappe.db.set_value(RECEIPT, name, dict(status="已作废", void_reason=reason, voided_by=frappe.session.user, voided_on=now_datetime()))
	return name


@frappe.whitelist(methods=["POST"])
def confirm_disbursement(name, modified):
	doc = _locked_ledger(name, PAYMENT, modified)
	validate_ledger(doc)
	if frappe.db.exists(PAYMENT, {"idempotency_key": doc.idempotency_key, "status": "已确认"}):
		frappe.throw(_("该支付/追回凭据已登记，请勿重复确认。"))
	paid = paid_by_person(doc.sales_order).get(doc.sales_person, 0)
	if doc.direction == "发放":
		active = frappe.db.get_value(SHEET, {"active_key": doc.sales_order}, "name")
		if active != doc.commission_sheet:
			frappe.throw(_("发放须引用当前有效提成版本。"))
		rows = get_release_context(active)
		row = next((r for r in rows if r.sales_person == doc.sales_person), None)
		if not row or doc.amount > row.available_amount + 0.005:
			frappe.throw(_("来源待复核或本次金额超过可发放额度。"))
	else:
		if doc.amount > paid + 0.005:
			frappe.throw(_("追回/冲销不得超过该人员累计净发放额。"))
		if doc.direction == "冲销发放":
			original = frappe.get_doc(PAYMENT, doc.reversal_of)
			if original.status != "已确认" or original.direction != "发放" or original.sales_order != doc.sales_order or original.sales_person != doc.sales_person:
				frappe.throw(_("原发放记录无效。"))
			reversed_amount = sum(frappe.get_all(PAYMENT, filters={"reversal_of": original.name, "status": "已确认"}, pluck="amount"))
			if doc.amount + reversed_amount > original.amount + 0.005:
				frappe.throw(_("冲销总额超过原发放记录。"))
	doc.flags.commission_confirm, doc.status = _CONFIRM, "已确认"
	doc.save()
	return doc.name
