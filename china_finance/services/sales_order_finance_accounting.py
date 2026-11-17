"""Versioned management accounting. Does not write invoices, GL or stock values."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from china_finance.services.sales_order_finance_permissions import assert_finance_access, can_edit_finance

DOCTYPE = "Sales Order Finance Accounting"
_CONFIRM_TOKEN = object()
ITEM_INPUTS = ("material_cost", "auxiliary_cost", "labor_cost", "overhead", "scrap_recovery", "sales_cost", "other_expenses", "cost_complete", "adjustment_reason")
TAX_INPUTS = ("description", "rate", "tax_base", "amount", "account", "reason")


def accounting_key(sales_order, sales_invoice):
	return hashlib.sha256(json.dumps([sales_order, sales_invoice], ensure_ascii=False).encode()).hexdigest()


def source_context(sales_order, sales_invoice):
	assert_finance_access(sales_order)
	order = frappe.get_doc("Sales Order", sales_order)
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	invoice.check_permission("read")
	if invoice.is_return and invoice.return_against:
		frappe.get_doc("Sales Invoice", invoice.return_against).check_permission("read")
	return _build_source_context(order, invoice)


def _build_source_context(order, invoice):
	"""Internal source fingerprint; public callers must authorize both records."""
	if order.docstatus != 1 or invoice.docstatus != 1:
		frappe.throw(_("订单和销售发票均须已提交且未取消。"))
	if invoice.company != order.company or invoice.customer != order.customer:
		frappe.throw(_("销售发票与订单的公司或客户不一致。"))
	order_rows = {r.name: r for r in order.items}
	rows = [r for r in invoice.items if r.sales_order == order.name]
	if not rows or any(r.so_detail not in order_rows for r in rows):
		frappe.throw(_("未找到有效的订单与发票产品行关联。"))
	if invoice.is_return:
		if not invoice.return_against:
			frappe.throw(_("红字核算必须关联原销售发票。"))
		original = frappe.get_doc("Sales Invoice", invoice.return_against)
		if not any(r.sales_order == order.name for r in original.items):
			frappe.throw(_("红字发票的原发票不属于该销售订单。"))
	precision = invoice.precision("net_total") or 2
	net = flt(sum(flt(r.net_amount) for r in rows), precision)
	# A multi-order invoice is split by each order's net amount; final tax rounding
	# residue is assigned deterministically to the last order, never counted twice.
	groups = {}
	for r in invoice.items:
		key = r.sales_order or "__unlinked__"
		groups[key] = groups.get(key, 0) + flt(r.net_amount)
	keys = sorted(groups)
	taxes = []
	for tax in invoice.taxes:
		amount = flt(tax.tax_amount_after_discount_amount, precision)
		if not invoice.net_total and amount:
			frappe.throw(_("零净额发票存在税费，需先明确分摊规则。"))
		shares = {k: flt(amount * groups[k] / invoice.net_total, precision) if invoice.net_total else 0 for k in keys}
		shares[keys[-1]] += flt(amount - sum(shares.values()), precision)
		taxes.append(dict(description=tax.description or tax.account_head, rate=flt(tax.rate), tax_base=net,
			official_amount=shares[order.name], amount=shares[order.name], account=tax.account_head))
	items = [dict(sales_order_item=r.so_detail, sales_invoice_item=r.name, item_code=r.item_code,
		qty=r.qty, net_amount=r.net_amount, project=r.get("project") or order_rows[r.so_detail].get("project") or order.get("project")) for r in rows]
	snapshot = dict(sales_order=order.name, sales_invoice=invoice.name, company=invoice.company,
		customer=invoice.customer, currency=invoice.currency, exchange_rate=invoice.conversion_rate,
		posting_date=str(invoice.posting_date), is_return=invoice.is_return, return_against=invoice.return_against,
		items=items, taxes=taxes, net_total=invoice.net_total, grand_total=invoice.grand_total)
	encoded = json.dumps(snapshot, sort_keys=True, default=str, ensure_ascii=False)
	return dict(order=order, invoice=invoice, items=items, taxes=taxes, snapshot=encoded,
		source_hash=hashlib.sha256(encoded.encode()).hexdigest(), precision=precision)


def calculate_totals(items, taxes, exchange_rate=1, precision=2):
	"""Keep missing cost distinct from an explicitly acknowledged zero cost."""
	complete = bool(items) and all(r.get("cost_complete") for r in items)
	revenue = flt(sum(flt(r.get("net_amount")) for r in items), precision)
	cost = flt(sum(flt(r.get("sales_cost")) for r in items), precision)
	other = flt(sum(flt(r.get("other_expenses")) for r in items), precision)
	profit = flt(revenue - cost, precision) if complete else None
	return dict(complete=int(complete), net_revenue=revenue, sales_cost=cost,
		production_cost=flt(sum(flt(r.get("production_cost")) for r in items), precision), other_expenses=other,
		official_tax=flt(sum(flt(r.get("official_amount")) for r in taxes), precision),
		tax_total=flt(sum(flt(r.get("amount")) for r in taxes), precision), gross_profit=profit,
		gross_margin=flt(profit / revenue * 100, 4) if complete and revenue else None,
		management_profit=flt(profit - other, precision) if complete else None,
		base_revenue=flt(revenue * exchange_rate, precision), base_sales_cost=flt(cost * exchange_rate, precision),
		base_tax=flt(sum(flt(r.get("amount")) for r in taxes) * exchange_rate, precision),
		base_gross_profit=flt(profit * exchange_rate, precision) if complete else None)


def validate_accounting(doc):
	assert_finance_access(doc.sales_order, "write")
	old = doc.get_doc_before_save()
	if old and old.status != "草稿":
		frappe.throw(_("已确认或失效核算不可原地修改，请创建修订版本。"))
	confirming = doc.flags.finance_confirm is _CONFIRM_TOKEN
	if doc.is_new() and doc.status != "草稿":
		frappe.throw(_("新核算必须从草稿开始。"))
	if doc.status not in ("草稿", "已确认") or (doc.status == "已确认" and not confirming):
		frappe.throw(_("请使用财务确认操作变更状态。"))
	if old and (old.sales_order != doc.sales_order or old.sales_invoice != doc.sales_invoice or old.previous_version != doc.previous_version):
		frappe.throw(_("核算来源和版本关联不可修改。"))
	context = source_context(doc.sales_order, doc.sales_invoice)
	invoice = context["invoice"]
	if confirming and doc.source_hash != context["source_hash"]:
		frappe.throw(_("来源发票数据已变化，请重新核对并保存草稿。"))
	if doc.previous_version:
		previous = frappe.get_doc(DOCTYPE, doc.previous_version)
		previous.check_permission("read")
		if previous.sales_order != doc.sales_order or previous.sales_invoice != doc.sales_invoice or previous.status not in ("已确认", "待复核"):
			frappe.throw(_("修订来源无效或已被替代，请刷新。"))
		if not doc.reason:
			frappe.throw(_("修订必须填写原因。"))
	elif confirming and frappe.db.exists(DOCTYPE, {"sales_order": doc.sales_order, "sales_invoice": doc.sales_invoice, "status": "待复核"}):
		frappe.throw(_("存在待复核历史核算，请从该记录创建修订版本。"))
	if not doc.posting_date:
		frappe.throw(_("请填写核算日期。"))
	source_rows = {r["sales_invoice_item"]: r for r in context["items"]}
	if len(doc.items) != len(source_rows) or {r.sales_invoice_item for r in doc.items} != set(source_rows):
		frappe.throw(_("必须完整核算本发票属于该订单的产品行，不可重复或遗漏。"))
	for row in doc.items:
		row.update(source_rows[row.sales_invoice_item])
		row.currency = invoice.currency
		for field in ITEM_INPUTS[:7]:
			value = flt(row.get(field), context["precision"])
			if value < 0 and not invoice.is_return or value > 0 and invoice.is_return:
				frappe.throw(_("普通发票成本不能为负；红字发票成本应为零或负数。"))
			row.set(field, value)
		row.production_cost = flt(row.material_cost + row.auxiliary_cost + row.labor_cost + row.overhead - row.scrap_recovery, context["precision"])
		# Suggestions are read-only and never trusted from a standard REST payload.
		row.suggested_sales_cost = None
		row.suggestion_source = None
	if len(doc.taxes or []) != len(context["taxes"]):
		frappe.throw(_("税费行须与来源发票一致。"))
	for row, source in zip(doc.taxes, context["taxes"], strict=True):
		row.currency = invoice.currency
		row.official_amount = source["official_amount"]
		row.amount = flt(row.amount, context["precision"])
		if row.account:
			account = frappe.get_doc("Account", row.account)
			if account.company != invoice.company or account.is_group or account.disabled:
				frappe.throw(_("请选择本公司有效的明细科目。"))
		if row.amount != row.official_amount and not (row.reason or doc.reason):
			frappe.throw(_("核算税额与发票不同，必须填写差异原因。"))
	doc.company, doc.customer, doc.currency = invoice.company, invoice.customer, invoice.currency
	doc.company_currency = frappe.get_cached_value("Company", invoice.company, "default_currency")
	doc.exchange_rate = invoice.conversion_rate
	doc.source_hash, doc.source_snapshot = context["source_hash"], context["snapshot"]
	doc.update(calculate_totals(doc.items, doc.taxes, doc.exchange_rate, context["precision"]))
	doc.active_key = accounting_key(doc.sales_order, doc.sales_invoice) if confirming else None
	doc.confirmed_by = frappe.session.user if confirming else None
	doc.confirmed_on = now_datetime() if confirming else None
	if confirming and not doc.complete:
		frappe.throw(_("请逐行确认成本已填写；明确零成本也需要勾选。"))


@frappe.whitelist()
def get_accounting_context(sales_order, sales_invoice=None):
	assert_finance_access(sales_order)
	order = frappe.get_doc("Sales Order", sales_order)
	# Use parent queries so standard invoice permissions apply before child access.
	names = frappe.get_all("Sales Invoice Item", filters={"sales_order": sales_order}, pluck="parent")
	invoices = frappe.get_list("Sales Invoice", filters={"name": ["in", names], "docstatus": 1},
		fields=["name", "posting_date", "currency", "grand_total", "is_return"], limit_page_length=0) if names else []
	records = frappe.get_list(DOCTYPE, filters={"sales_order": sales_order},
		fields=["name", "sales_invoice", "status", "posting_date", "currency", "complete", "net_revenue", "sales_cost", "gross_profit", "gross_margin", "source_hash", "active_key"],
		order_by="creation desc", limit_page_length=0)
	for row in records:
		if row.status == "已确认":
			try:
				if not row.active_key or source_context(sales_order, row.sales_invoice)["source_hash"] != row.source_hash:
					row.status = "待复核"
			except (frappe.ValidationError, frappe.DoesNotExistError):
				row.status = "待复核"
	result = dict(can_edit=can_edit_finance(), invoices=invoices, records=records, order_submitted=order.docstatus == 1)
	if sales_invoice:
		context = source_context(sales_order, sales_invoice)
		result.update(items=context["items"], taxes=context["taxes"], currency=context["invoice"].currency)
	return result


@frappe.whitelist(methods=["POST"])
def create_accounting_draft(sales_order, sales_invoice):
	assert_finance_access(sales_order, "write")
	context = source_context(sales_order, sales_invoice)
	# Lock the parent for concurrent draft/confirmation/revision requests.
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", sales_order)
	existing = frappe.db.get_value(DOCTYPE, {"sales_order": sales_order, "sales_invoice": sales_invoice, "status": ["in", ["草稿", "已确认"]]}, "name")
	if existing:
		frappe.get_doc(DOCTYPE, existing).check_permission("read")
		return existing
	doc = frappe.get_doc(dict(doctype=DOCTYPE, sales_order=sales_order, sales_invoice=sales_invoice,
		status="草稿", items=context["items"], taxes=context["taxes"]))
	doc.insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def confirm_accounting(name, modified):
	doc = frappe.get_doc(DOCTYPE, name)
	assert_finance_access(doc.sales_order, "write")
	doc.check_permission("write")
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", doc.sales_order)
	doc.reload()
	if str(doc.modified) != str(modified) or doc.status != "草稿":
		frappe.throw(_("核算已被修改，请刷新后重试。"), frappe.TimestampMismatchError)
	active = frappe.db.get_value(DOCTYPE, {"active_key": accounting_key(doc.sales_order, doc.sales_invoice)}, "name")
	if active and active != doc.previous_version:
		frappe.throw(_("该订单与发票已存在有效核算，请从当前版本创建修订。"))
	doc.flags.finance_confirm = _CONFIRM_TOKEN
	doc.status = "已确认"
	validate_accounting(doc)
	frappe.db.savepoint("confirm_sales_order_finance")
	try:
		if active:
			frappe.db.set_value(DOCTYPE, active, "active_key", None)
		doc.save()
		if doc.previous_version:
			frappe.db.set_value(DOCTYPE, doc.previous_version, {"active_key": None, "status": "已替代"})
	except Exception:
		frappe.db.rollback(save_point="confirm_sales_order_finance")
		raise
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_revision(name, reason):
	old = frappe.get_doc(DOCTYPE, name)
	assert_finance_access(old.sales_order, "write")
	old.check_permission("read")
	if not reason or not str(reason).strip():
		frappe.throw(_("请填写修订原因。"))
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", old.sales_order)
	old.reload()
	if old.status not in ("已确认", "待复核"):
		frappe.throw(_("仅可修订当前已确认或待复核版本。"))
	existing = frappe.db.get_value(DOCTYPE, {"previous_version": name, "status": "草稿"}, "name")
	if existing:
		return existing
	new = frappe.copy_doc(old)
	new.status, new.previous_version, new.reason = "草稿", old.name, reason
	new.insert()
	return new.name


def invalidate_invoice(doc, method=None):
	# Same transaction as source cancellation; no rewriting immutable snapshots.
	for name in frappe.get_all(DOCTYPE, filters={"sales_invoice": doc.name, "status": "已确认"}, pluck="name"):
		frappe.db.set_value(DOCTYPE, name, {"status": "待复核", "active_key": None})


@frappe.whitelist()
def get_accounting_preview(name):
	doc = frappe.get_doc(DOCTYPE, name)
	doc.check_permission("read")
	assert_finance_access(doc.sales_order)
	try:
		context = source_context(doc.sales_order, doc.sales_invoice)
	except (frappe.ValidationError, frappe.DoesNotExistError):
		return dict(entries=[], message=_("来源已失效，历史核算保留，请复核。"))
	if context["source_hash"] != doc.source_hash:
		return dict(entries=[], message=_("来源数据已变化，请重新复核。"))
	if not doc.complete:
		return dict(entries=[], message=_("成本待完善，暂不形成完整核算预览。"))
	if context["order"].get("custom_china_settlement_mode") == "对账结算后确认应收":
		message = _("当前为对账结算模式，本核算不提前确认应收，不生成凭证。")
	else:
		message = _("以下按核算收入和税费生成管理预览，不代表正式凭证，正式记账沿用现有发票及结算流程。")
	invoice = context["invoice"]
	entries = []
	def entry(account, amount, direction, remark):
		entries.append(dict(account=account or _("待财务配置科目"), debit=abs(amount) if (amount >= 0) == (direction == "debit") else 0,
			credit=abs(amount) if (amount >= 0) != (direction == "debit") else 0, remark=remark))
	entry(invoice.debit_to, doc.net_revenue + doc.tax_total, "debit", _("应收（核算预览）"))
	for item in doc.items:
		row = next(r for r in invoice.items if r.name == item.sales_invoice_item)
		entry(row.income_account, flt(item.net_amount), "credit", _("销售收入"))
	for tax in doc.taxes:
		if tax.amount:
			entry(tax.account, flt(tax.amount), "credit", tax.description)
	if context["order"].get("custom_china_settlement_mode") == "对账结算后确认应收":
		entries = []
	return dict(entries=entries, message=message, currency=doc.currency)
