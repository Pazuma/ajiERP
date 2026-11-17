"""Read-only source adapters. Never change invoices, stock, GL or settlement."""

import hashlib
import json
import math

import frappe
from frappe import _
from frappe.utils import flt

from china_finance.services.sales_commission_permissions import assert_access

BASIS_TYPES = ("订单未税金额", "已开票未税金额", "实际回款金额", "财务确认毛利", "手工指定基数")
RELEASE_TYPES = ("确认后可发放", "全额回款后可发放", "随回款比例发放")


def digest(value):
	return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def number(value):
	try:
		result = float(value or 0)
	except (TypeError, ValueError):
		frappe.throw(_("金额与比例必须为有效数字。"))
	if not math.isfinite(result):
		frappe.throw(_("金额与比例必须为有限数字。"))
	return result


def order_context(sales_order):
	order = frappe.get_doc("Sales Order", sales_order)
	if order.docstatus != 1:
		frappe.throw(_("提成仅适用于已提交且未取消的销售订单。"))
	return order


def invoice_sources(order):
	# This narrow internal query returns no costs or unrelated invoice rows.
	names = sorted(set(frappe.get_all("Sales Invoice Item", filters={"sales_order": order.name}, pluck="parent")))
	result = []
	for name in names:
		invoice = frappe.get_doc("Sales Invoice", name)
		if invoice.docstatus != 1:
			continue
		if invoice.company != order.company or invoice.customer != order.customer:
			frappe.throw(_("关联销售发票的公司或客户不一致。"))
		rows = [r for r in invoice.items if r.sales_order == order.name]
		valid = {r.name for r in order.items}
		if any(r.so_detail not in valid for r in rows):
			frappe.throw(_("发票产品行缺少有效订单行关联。"))
		groups = {}
		for row in invoice.items:
			key = row.sales_order or "__unlinked__"
			groups[key] = groups.get(key, 0) + flt(row.base_net_amount)
		precision = invoice.precision("base_grand_total") or 2
		total = sum(groups.values())
		if not total and invoice.base_grand_total:
			frappe.throw(_("零净额发票的含税金额无法自动分摊。"))
		shares = {key: flt(invoice.base_grand_total * value / total, precision) if total else 0 for key, value in groups.items()}
		last = sorted(groups)[-1]
		shares[last] += flt(invoice.base_grand_total - sum(shares.values()), precision)
		result.append(dict(name=name, net=sum(flt(r.base_net_amount) for r in rows), gross=shares[order.name],
			is_return=invoice.is_return, return_against=invoice.return_against,
			rows=[dict(name=r.name, detail=r.so_detail, qty=r.qty, net=r.base_net_amount) for r in rows]))
	return result


def margin_source(order, invoices):
	from china_finance.services.sales_order_finance_accounting import DOCTYPE, accounting_key
	values = []
	if not invoices:
		frappe.throw(_("待开票或待财务核算，不能按零毛利确认。"))
	# Called only through commission authorization, not a public accounting API.
	for source in invoices:
		name = frappe.db.get_value(DOCTYPE, {"active_key": accounting_key(order.name, source["name"]), "status": "已确认"}, "name")
		if not name:
			frappe.throw(_("存在未确认或待复核的财务核算，请先由财务核对。"))
		accounting = frappe.get_doc(DOCTYPE, name)
		from china_finance.services.sales_order_finance_accounting import _build_source_context
		context = _build_source_context(order, frappe.get_doc("Sales Invoice", source["name"]))
		if not accounting.complete or context["source_hash"] != accounting.source_hash:
			frappe.throw(_("财务核算来源已变化，请先复核。"))
		values.append(dict(name=name, hash=accounting.source_hash, amount=accounting.base_gross_profit))
	values.sort(key=lambda r: r["name"])
	return dict(amount=max(sum(flt(r["amount"]) for r in values), 0), fingerprint=digest(values))


def get_context(doc, approve_margin=False, _authorized=False):
	if not _authorized:
		assert_access(doc.sales_order, margin=doc.basis_type == "财务确认毛利")
	order = order_context(doc.sales_order)
	if doc.basis_type not in BASIS_TYPES or doc.release_condition not in RELEASE_TYPES:
		frappe.throw(_("请选择有效计提依据和发放条件。"))
	if doc.receipt_tax_mode not in ("含税实收", "折算未税回款"):
		frappe.throw(_("请选择回款含税口径。"))
	if doc.basis_type == "实际回款金额" and doc.release_condition == "随回款比例发放":
		frappe.throw(_("回款计提不能再次按回款比例折算发放。"))
	invoices = invoice_sources(order)
	allocations = frappe.get_all("Sales Commission Receipt Allocation", filters={"sales_order": order.name, "status": "已确认"},
		fields=["name", "amount", "net_amount", "source_type", "payment_entry", "sales_invoice", "direction", "source_hash"], order_by="name")
	for row in allocations:
		if row.payment_entry:
			from china_finance.services.sales_commission_payments import receipt_source
			if receipt_source(frappe.get_doc("Sales Commission Receipt Allocation", row.name))["hash"] != row.source_hash:
				frappe.throw(_("回款凭据已变化，请财务复核分配记录。"))
	receipt = sum(flt(r.amount) * (-1 if r.direction == "退款" else 1) for r in allocations)
	net_receipt = sum(flt(r.net_amount) * (-1 if r.direction == "退款" else 1) for r in allocations)
	baseline = flt(order.base_grand_total) + sum(r["gross"] for r in invoices if r["is_return"])
	amount = max(flt(order.base_net_total) + sum(r["net"] for r in invoices if r["is_return"]), 0)
	extra = None
	if doc.basis_type == "已开票未税金额":
		if not invoices:
			frappe.throw(_("待开票，不能确认开票提成。"))
		amount = max(sum(r["net"] for r in invoices), 0)
	elif doc.basis_type == "实际回款金额":
		if not allocations:
			frappe.throw(_("待财务确认回款分配。"))
		if doc.receipt_tax_mode == "折算未税回款" and any(not r.sales_invoice for r in allocations):
			frappe.throw(_("未税回款须逐发票明确分配，不能使用未关联发票的人工回款。"))
		amount = max(net_receipt if doc.receipt_tax_mode == "折算未税回款" else receipt, 0)
	elif doc.basis_type == "手工指定基数":
		if not (doc.manual_reason or "").strip():
			frappe.throw(_("手工基数必须填写原因。"))
		amount = number(doc.manual_basis)
	elif doc.basis_type == "财务确认毛利":
		# Finance explicitly approves a restricted snapshot. Managers consume it;
		# confirmation checks financial versions and invoice fingerprints again.
		if approve_margin:
			extra = margin_source(order, invoices)
		else:
			if not doc.margin_approved_by or not doc.margin_source_hash:
				frappe.throw(_("请先由财务批准毛利基数。"))
			versions = frappe.get_all("Sales Order Finance Accounting", filters={"sales_order": order.name, "status": "已确认"},
				fields=["name", "source_hash", "base_gross_profit", "active_key", "complete"], order_by="name")
			from china_finance.services.sales_order_finance_accounting import accounting_key
			wanted = {accounting_key(order.name, inv["name"]) for inv in invoices}
			versions = [v for v in versions if v.active_key in wanted and v.complete]
			values = sorted([dict(name=v.name, hash=v.source_hash, amount=v.base_gross_profit) for v in versions], key=lambda x: x["name"])
			if len(versions) != len(invoices) or digest(values) != doc.margin_source_hash:
				frappe.throw(_("毛利基数已失效，请财务重新批准。"))
			from china_finance.services.sales_order_finance_accounting import _build_source_context
			for inv in invoices:
				current = _build_source_context(order, frappe.get_doc("Sales Invoice", inv["name"]))
				if not any(v.source_hash == current["source_hash"] and v.active_key == accounting_key(order.name, inv["name"]) for v in versions):
					frappe.throw(_("毛利来源已变化，请先由财务复核。"))
			extra = dict(amount=doc.margin_basis, fingerprint=doc.margin_source_hash)
		amount = extra["amount"]
	if amount < 0:
		frappe.throw(_("计提基数不能为负，请复核。"))
	if doc.release_condition != "确认后可发放" and baseline <= 0:
		frappe.throw(_("回款应收基准为零或负数，需财务复核。"))
	precision = order.precision("base_grand_total") or 2
	snapshot = dict(order=dict(name=order.name, company=order.company, customer=order.customer, net=order.base_net_total,
		gross=order.base_grand_total, modified=str(order.modified)), invoices=invoices, allocations=allocations,
		basis_type=doc.basis_type, release_condition=doc.release_condition, receipt_tax_mode=doc.receipt_tax_mode,
		manual_basis=flt(doc.manual_basis), manual_reason=doc.manual_reason or "", margin=extra)
	return dict(company=order.company, customer=order.customer, company_currency=frappe.get_cached_value("Company", order.company, "default_currency"),
		basis_amount=flt(amount, precision), receipt_amount=flt(receipt, precision), receivable_baseline=flt(baseline, precision),
		receipt_ratio=min(max(receipt / baseline, 0), 1) if baseline > 0 else 0,
		source_snapshot=json.dumps(snapshot, sort_keys=True, default=str, ensure_ascii=False), source_hash=digest(snapshot),
		precision=precision, margin=extra)
