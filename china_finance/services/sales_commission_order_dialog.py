"""Order-first UI adapters. Existing commission calculation/lifecycle stays authoritative."""

import frappe
from frappe import _
from frappe.utils import cint

from china_finance.services.sales_commission_permissions import (
	SHEET, assert_access, can_manage, can_finance, can_margin, own_sales_person,
)
from china_finance.services.sales_commission import (
	calculate_people, create_commission_revision, effective_state, lock_order,
)
from china_finance.services.sales_commission_sources import get_context
from china_finance.services.sales_commission_payments import release_rows

RULES = ("basis_type", "release_condition", "receipt_tax_mode", "manual_basis", "manual_reason")
PERSON = ("sales_person", "commission_rate", "remark")


def audience():
	if can_manage() or can_finance():
		return None
	if not {"Sales User", "Sales Manager"} & set(frappe.get_roles()):
		frappe.throw(_("没有提成查询权限。"), frappe.PermissionError)
	return own_sales_person()


def latest(order, personal=False):
	filters = {"sales_order": order, "status": ["in", ["已确认", "待复核", "已作废"] if personal else ["草稿", "已确认", "待复核", "已作废"]]}
	name = frappe.db.get_value(SHEET, filters, "name", order_by="creation desc")
	return frappe.get_doc(SHEET, name) if name else None


def authorize_order(order):
	frappe.has_permission("Sales Order", "read", doc=order, throw=True)
	return frappe.get_doc("Sales Order", order)


def personal_rows(doc, person):
	if not doc:
		return []
	return [{k: row.get(k) for k in ("sales_person", "commission_amount", "eligible_amount", "paid_amount", "available_amount", "recoverable_amount", "status")}
		for row in release_rows(doc, internal=True) if row.sales_person == person]


def order_people(order):
	return list(dict.fromkeys(p for p in [order.get("custom_sales_person"),
		*[r.sales_person for r in order.get("sales_team", [])]] if p))


def order_summary(order):
	# Explicit sales-only projection: never return the full order or item documents.
	return {k: order.get(k) for k in ("transaction_date", "currency", "net_total",
		"total_taxes_and_charges", "grand_total", "base_net_total", "base_grand_total")} | dict(
		primary_sales_person=order.get("custom_sales_person"),
		items=[{k: r.get(k) for k in ("item_code", "item_name", "description", "qty", "uom", "rate", "amount")}
			for r in order.get("items", [])])


@frappe.whitelist()
def list_commission_orders(filters=None, start=0, page_length=20):
	filters = frappe._dict(frappe.parse_json(filters) or {})
	person = audience()
	if not filters.company:
		frappe.throw(_("请选择公司。"))
	query = {"company": filters.company, "docstatus": ["in", [1, 2]]}
	for key, field in (("sales_order", "name"), ("customer", "customer")):
		if filters.get(key):
			query[field] = filters[key]
	if filters.from_date:
		query["transaction_date"] = [">=", filters.from_date]
	if filters.to_date:
		query["transaction_date"] = ["between", [filters.from_date, filters.to_date]] if filters.from_date else ["<=", filters.to_date]
	# Apply visibility and commission filters before pagination and counting.
	orders = frappe.get_list("Sales Order", filters=query, fields=["name", "customer", "transaction_date", "docstatus"], order_by="transaction_date desc, name desc", limit_page_length=0)
	result = []
	for order in orders:
		if not frappe.has_permission("Sales Order", "read", doc=order.name):
			continue
		doc = latest(order.name, personal=bool(person))
		if not doc and (person or not can_manage() or order.docstatus != 1):
			continue
		if person:
			rows = personal_rows(doc, person)
			if not rows:
				continue
			status, amount, people = rows[0]["status"], rows[0]["commission_amount"], person
		else:
			restricted = doc and doc.basis_type == "财务确认毛利" and not can_margin()
			status = "受限" if restricted else effective_state(doc) if doc else "未设置"
			amount = None if restricted or not doc or not doc.source_ready else doc.commission_total
			people_names = ([r.sales_person for r in doc.sales_people] if doc and not restricted
				else order_people(frappe.get_doc("Sales Order", order.name)))
			people = "、".join(people_names) or "未关联业务人员"
			if filters.sales_person and filters.sales_person not in people_names:
				continue
		if filters.status and status != filters.status:
			continue
		result.append(dict(sales_order=order.name, customer=order.customer, transaction_date=order.transaction_date,
			status=status, commission_total=amount, sales_people=people))
	start, size = max(cint(start), 0), min(max(cint(page_length), 1), 100)
	return dict(rows=result[start:start + size], total=len(result), can_manage=can_manage())


@frappe.whitelist()
def get_order_commission_dialog(sales_order):
	person = audience()
	order = authorize_order(sales_order)
	doc = latest(sales_order, personal=bool(person))
	base = dict(sales_order=order.name, customer=order.customer, company=order.company,
		company_currency=frappe.get_cached_value("Company", order.company, "default_currency"),
		order_summary=order_summary(order))
	if person:
		rows = personal_rows(doc, person)
		if not rows:
			frappe.throw(_("没有本人的提成记录。"), frappe.PermissionError)
		return base | dict(editable=False, personal=True, results=rows, status=rows[0]["status"])
	assert_access(sales_order)
	if doc and doc.basis_type == "财务确认毛利" and not can_margin():
		frappe.throw(_("该提成使用受限毛利基数，请联系授权财务。"), frappe.PermissionError)
	if not doc:
		if not can_manage() or order.docstatus != 1:
			frappe.throw(_("该订单尚无可查看提成。"), frappe.PermissionError)
		people = order_people(order)
		return base | dict(editable=True, status="未设置", basis_type="订单未税金额", release_condition="确认后可发放",
			receipt_tax_mode="含税实收", sales_people=[dict(sales_person=p, commission_rate=0, remark="") for p in people])
	return base | {k: doc.get(k) for k in (*RULES, "name", "modified", "basis_amount", "commission_total", "source_ready", "source_message")} | dict(
		editable=can_manage() and order.docstatus == 1 and doc.status != "已作废", status=effective_state(doc),
		sales_people=[{k: r.get(k) for k in (*PERSON, "commission_amount")} for r in doc.sales_people])


def candidate(payload):
	data = frappe._dict(frappe.parse_json(payload) or {})
	allowed = {*RULES, "sales_order", "name", "modified", "revision_reason", "sales_people"}
	if set(data) - allowed:
		frappe.throw(_("包含不允许修改的字段。"))
	assert_access(data.sales_order, "manage", margin=data.basis_type == "财务确认毛利")
	order = authorize_order(data.sales_order)
	if order.docstatus != 1:
		frappe.throw(_("仅可设置已提交且未取消的订单。"))
	current = latest(order.name)
	if current and current.basis_type == "财务确认毛利" and not can_margin():
		frappe.throw(_("没有毛利基数授权。"), frappe.PermissionError)
	if (current.name if current else None) != data.get("name") or (current and str(current.modified) != str(data.modified)):
		frappe.throw(_("提成已更新，请关闭弹窗后重新打开。"), frappe.TimestampMismatchError)
	if current and current.status != "草稿" and not (data.revision_reason or "").strip():
		frappe.throw(_("调整已确认提成必须填写修订原因。"))
	if not data.sales_people:
		frappe.throw(_("请至少添加一名业务人员。"))
	for row in data.sales_people:
		if set(row) - set(PERSON):
			frappe.throw(_("包含不允许修改的人员字段。"))
		p = frappe.get_doc("Sales Person", row.get("sales_person"))
		if not p.enabled or p.is_group:
			frappe.throw(_("请选择启用的业务人员。"))
		candidates = {order.get("custom_sales_person"), *[r.sales_person for r in order.get("sales_team", [])]}
		if p.name not in candidates and not (row.get("remark") or "").strip():
			frappe.throw(_("额外参与人员必须填写备注。"))
	calculate_people(data.sales_people, 0)
	return data, current


@frappe.whitelist()
def preview_order_commission(payload):
	data, current = candidate(payload)
	doc = frappe.copy_doc(current) if current else frappe.get_doc(dict(doctype=SHEET, sales_order=data.sales_order))
	doc.update({k: data.get(k) for k in RULES})
	# A revision requires a new financial approval, just like the existing revision service.
	if current and current.status != "草稿":
		for field in ("margin_approved_by", "margin_source_hash"):
			doc.set(field, None)
	try:
		context = get_context(doc)
	except frappe.PermissionError:
		raise
	except frappe.ValidationError as exc:
		return dict(source_ready=False, source_message=str(exc))
	people = [dict(r) for r in data.sales_people]
	total = calculate_people(people, context["basis_amount"], context["precision"])
	return dict(source_ready=True, basis_amount=context["basis_amount"], commission_total=total, sales_people=people)


@frappe.whitelist(methods=["POST"])
def save_order_commission_dialog(payload):
	# Acquire before comparing the client version, including the first-create case.
	data = frappe._dict(frappe.parse_json(payload) or {})
	assert_access(data.sales_order, "manage")
	lock_order(data.sales_order)
	data, current = candidate(payload)
	if current and current.status != "草稿":
		current = frappe.get_doc(SHEET, create_commission_revision(current.name, data.revision_reason))
	doc = current or frappe.get_doc(dict(doctype=SHEET, sales_order=data.sales_order, status="草稿"))
	doc.update({k: data.get(k) for k in RULES})
	doc.set("sales_people", data.sales_people)
	doc.save()
	return get_order_commission_dialog(data.sales_order)
