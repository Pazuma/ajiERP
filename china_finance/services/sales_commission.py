"""Versioned sales commissions. No writes to orders, invoices or GL."""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from china_finance.services.sales_commission_permissions import SHEET, assert_access, can_finance, can_manage
from china_finance.services.sales_commission_sources import get_context, number, order_context

_CONFIRM = object()
APPROVAL_FIELDS = ("margin_basis", "margin_source_hash", "margin_approved_by", "margin_approved_on")


def lock_order(order):
	frappe.db.sql("select name from `tabSales Order` where name=%s for update", order)


def calculate_people(rows, basis, precision=2):
	seen, total_rate, total = set(), 0, 0
	for row in rows:
		person = row.get("sales_person")
		if not person or person in seen:
			frappe.throw(_("业务人员不能为空或重复。"))
		seen.add(person)
		rate = number(row.get("commission_rate"))
		if not 0 <= rate <= 100:
			frappe.throw(_("个人提成比例须在0至100之间。"))
		total_rate += rate
		amount = flt(number(basis) * rate / 100, precision)
		if isinstance(row, dict):
			row["commission_amount"] = amount
		else:
			row.commission_amount = amount
		total += amount
	if total_rate > 100:
		frappe.throw(_("个人提成比例合计不能大于100%。"))
	return flt(total, precision)


def validate_sheet(doc):
	assert_access(doc.sales_order, "manage", margin=doc.basis_type == "财务确认毛利")
	lock_order(doc.sales_order)
	order = order_context(doc.sales_order)
	old = doc.get_doc_before_save() or (frappe.get_doc(SHEET, doc.name) if not doc.is_new() else None)
	confirming = doc.flags.commission_confirm is _CONFIRM
	if old and old.status != "草稿":
		frappe.throw(_("已确认提成不可直接修改，请创建修订。"))
	if doc.status not in ("草稿", "已确认") or (doc.status == "已确认" and not confirming) or (doc.is_new() and doc.status != "草稿"):
		frappe.throw(_("请使用提成确认操作。"))
	if old and (doc.sales_order != old.sales_order or doc.previous_version != old.previous_version):
		frappe.throw(_("提成订单及版本关联不可修改。"))
	for field in APPROVAL_FIELDS:
		current = flt(doc.get(field)) if field == "margin_basis" else str(doc.get(field) or "")
		stored = flt(old.get(field)) if field == "margin_basis" and old else str(old.get(field) or "") if old else (0 if field == "margin_basis" else "")
		if current != stored:
			frappe.throw(_("毛利批准信息只能由财务批准操作生成。"))
	if doc.basis_type != "财务确认毛利":
		for field in APPROVAL_FIELDS:
			doc.set(field, None)
	if doc.previous_version:
		previous = frappe.get_doc(SHEET, doc.previous_version)
		if previous.sales_order != doc.sales_order or previous.status not in ("已确认", "待复核") or not (doc.revision_reason or "").strip():
			frappe.throw(_("修订必须引用本订单当前确认版本并填写原因。"))
	elif frappe.db.exists(SHEET, {"sales_order": doc.sales_order, "status": ["in", ["已确认", "待复核"]]}):
		frappe.throw(_("请从本订单当前版本创建修订。"))
	other = frappe.db.get_value(SHEET, {"sales_order": doc.sales_order, "status": "草稿", "name": ["!=", doc.name or ""]}, "name")
	if other:
		frappe.throw(_("本订单已有提成草稿：{0}").format(other))
	doc.company, doc.customer = order.company, order.customer
	doc.company_currency = frappe.get_cached_value("Company", order.company, "default_currency")
	if not doc.sales_people:
		frappe.throw(_("请至少添加一名业务人员。"))
	candidates = {order.get("custom_sales_person"), *[r.sales_person for r in order.get("sales_team", [])]}
	for row in doc.sales_people:
		person = frappe.get_doc("Sales Person", row.sales_person)
		if not person.enabled or person.is_group:
			frappe.throw(_("请选择启用的非分组业务人员。"))
		if person.name not in candidates and not (row.remark or "").strip():
			frappe.throw(_("额外参与人员必须填写备注说明。"))
		row.employee = person.employee
		row.beneficiary_user = frappe.db.get_value("Employee", person.employee, "user_id") if person.employee else None
		row.company_currency = doc.company_currency
	try:
		context = get_context(doc)
	except frappe.ValidationError as exc:
		if confirming:
			raise
		doc.source_ready, doc.source_message = 0, str(exc)
		doc.basis_amount = doc.receipt_amount = doc.receivable_baseline = doc.receipt_ratio = 0
		doc.source_hash, doc.source_snapshot = None, None
		for row in doc.sales_people:
			row.commission_amount = None
		calculate_people([dict(sales_person=r.sales_person, commission_rate=r.commission_rate) for r in doc.sales_people], 0)
		doc.commission_total = None
	else:
		if confirming and doc.source_hash != context["source_hash"]:
			frappe.throw(_("来源已变化，请刷新并保存草稿后再确认。"))
		for field in ("basis_amount", "receipt_amount", "receivable_baseline", "receipt_ratio", "source_snapshot", "source_hash"):
			doc.set(field, context[field])
		doc.source_ready, doc.source_message = 1, "来源完整，可核对确认"
		doc.commission_total = calculate_people(doc.sales_people, doc.basis_amount, context["precision"])
	doc.active_key = doc.sales_order if confirming else None
	doc.confirmed_by = frappe.session.user if confirming else None
	doc.confirmed_on = now_datetime() if confirming else None
	doc.confirmed_date = doc.confirmed_on.date() if confirming else None
	if confirming:
		previous_total = frappe.db.get_value(SHEET, doc.previous_version, "commission_total") if doc.previous_version else 0
		doc.commission_delta = flt(doc.commission_total - flt(previous_total), doc.precision("commission_total"))
	else:
		doc.commission_delta = 0


@frappe.whitelist(methods=["POST"])
def create_commission_draft(sales_order):
	assert_access(sales_order, "manage")
	order = order_context(sales_order)
	lock_order(sales_order)
	existing = frappe.db.get_value(SHEET, {"sales_order": sales_order, "status": ["in", ["草稿", "已确认", "待复核"]]}, "name", order_by="creation desc")
	if existing:
		frappe.get_doc(SHEET, existing).check_permission("read")
		return existing
	people = sorted({p for p in [order.get("custom_sales_person"), *[r.sales_person for r in order.get("sales_team", [])]] if p})
	if not people:
		frappe.throw(_("订单尚未配置业务人员，请先核对订单归属。"))
	doc = frappe.get_doc(dict(doctype=SHEET, sales_order=sales_order, status="草稿", basis_type="订单未税金额",
		release_condition="确认后可发放", receipt_tax_mode="含税实收", sales_people=[dict(sales_person=p, commission_rate=0) for p in people]))
	doc.insert()
	return doc.name


@frappe.whitelist()
def preview_commission(name):
	doc = frappe.get_doc(SHEET, name)
	doc.check_permission("read")
	context = get_context(doc)
	rows = [dict(sales_person=r.sales_person, commission_rate=r.commission_rate) for r in doc.sales_people]
	total = calculate_people(rows, context["basis_amount"], context["precision"])
	return dict(basis_amount=context["basis_amount"], commission_total=total, people=rows)


@frappe.whitelist(methods=["POST"])
def confirm_commission(name, modified):
	doc = frappe.get_doc(SHEET, name)
	assert_access(doc.sales_order, "manage", margin=doc.basis_type == "财务确认毛利")
	lock_order(doc.sales_order)
	doc.reload()
	if str(doc.modified) != str(modified) or doc.status != "草稿":
		frappe.throw(_("提成已被修改，请刷新。"), frappe.TimestampMismatchError)
	active = frappe.db.get_value(SHEET, {"active_key": doc.sales_order}, "name")
	if active and active != doc.previous_version:
		frappe.throw(_("本订单已有有效版本，请从当前版本修订。"))
	if doc.previous_version and active != doc.previous_version:
		frappe.throw(_("修订来源已失效，请刷新。"))
	doc.flags.commission_confirm, doc.status = _CONFIRM, "已确认"
	validate_sheet(doc)
	frappe.db.savepoint("commission_confirm")
	try:
		if active:
			frappe.db.set_value(SHEET, active, "active_key", None)
		doc.save()
		if active:
			frappe.db.set_value(SHEET, active, "status", "已替代")
	except Exception:
		frappe.db.rollback(save_point="commission_confirm")
		raise
	return doc.name


@frappe.whitelist(methods=["POST"])
def create_commission_revision(name, reason):
	old = frappe.get_doc(SHEET, name)
	assert_access(old.sales_order, "manage", margin=old.basis_type == "财务确认毛利")
	lock_order(old.sales_order)
	old.reload()
	if old.status not in ("已确认", "待复核") or not old.active_key or not (reason or "").strip():
		frappe.throw(_("仅当前版本可修订，且必须填写原因。"))
	existing = frappe.db.get_value(SHEET, {"sales_order": old.sales_order, "status": "草稿"}, "name")
	if existing:
		return existing
	doc = frappe.copy_doc(old)
	doc.status, doc.previous_version, doc.revision_reason = "草稿", old.name, reason
	for field in (*APPROVAL_FIELDS, "active_key", "confirmed_by", "confirmed_on", "confirmed_date"):
		doc.set(field, None)
	doc.insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def approve_margin_basis(name, modified):
	from china_finance.services.sales_order_finance_permissions import assert_finance_access
	doc = frappe.get_doc(SHEET, name)
	assert_access(doc.sales_order, "finance", margin=True)
	assert_finance_access(doc.sales_order)
	lock_order(doc.sales_order)
	doc.reload()
	if doc.status != "草稿" or doc.basis_type != "财务确认毛利" or str(doc.modified) != str(modified):
		frappe.throw(_("请刷新毛利计提草稿后批准。"))
	context = get_context(doc, approve_margin=True)
	frappe.db.set_value(SHEET, name, dict(margin_basis=context["margin"]["amount"], margin_source_hash=context["margin"]["fingerprint"],
		margin_approved_by=frappe.session.user, margin_approved_on=now_datetime()))
	return name


def effective_state(doc, internal=False):
	if doc.status not in ("已确认", "待复核"):
		return doc.status
	try:
		if doc.status != "已确认" or not doc.active_key or get_context(doc, _authorized=internal)["source_hash"] != doc.source_hash:
			return "待复核"
	except (frappe.ValidationError, frappe.PermissionError, frappe.DoesNotExistError):
		return "待复核"
	return "已确认"


@frappe.whitelist(methods=["POST"])
def void_cancelled_order_commission(name, reason):
	"""End entitlement for a cancelled order, retaining original amounts/payments."""
	doc = frappe.get_doc(SHEET, name)
	assert_access(doc.sales_order, "manage", margin=doc.basis_type == "财务确认毛利")
	lock_order(doc.sales_order)
	doc.reload()
	if not doc.active_key or doc.status not in ("已确认", "待复核") or frappe.db.get_value("Sales Order", doc.sales_order, "docstatus") != 2:
		frappe.throw(_("仅可作废已取消订单的当前提成版本。"))
	if not (reason or "").strip():
		frappe.throw(_("作废必须填写原因。"))
	frappe.db.set_value(SHEET, name, dict(status="已作废", active_key=None, void_reason=reason, voided_by=frappe.session.user, voided_on=now_datetime(), voided_date=now_datetime().date()))
	return name


@frappe.whitelist()
def get_commission_context(sales_order):
	assert_access(sales_order)
	rows = frappe.get_list(SHEET, filters={"sales_order": sales_order}, fields=["name", "status"], order_by="creation desc")
	return dict(can_manage=can_manage(), can_finance=can_finance(), records=rows)
