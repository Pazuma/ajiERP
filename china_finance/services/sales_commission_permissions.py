"""Commission capabilities are separate from order access and accounting access."""

import frappe
from frappe import _

MANAGER = "Sales Commission Manager"
FINANCE = "Sales Commission Finance"
MARGIN = "Sales Commission Margin Reader"
SALES_DIRECTOR = "销售总监"
SHEET = "Sales Commission Sheet"
RECEIPT = "Sales Commission Receipt Allocation"
PAYMENT = "Sales Commission Disbursement"


def has_role(role, user=None):
	user = user or frappe.session.user
	return user == "Administrator" or role in frappe.get_roles(user)


def can_manage(user=None):
	return has_role(MANAGER, user) or has_role(SALES_DIRECTOR, user)


def can_finance(user=None):
	return has_role(FINANCE, user)


def can_margin(user=None):
	from china_finance.services.sales_order_finance_permissions import can_read_finance
	return has_role(MARGIN, user) or (can_finance(user) and can_read_finance(user))


def assert_access(sales_order=None, action="read", user=None, margin=False):
	user = user or frappe.session.user
	allowed = can_manage(user) if action == "manage" else can_finance(user) if action == "finance" else (can_manage(user) or can_finance(user))
	if not allowed or (margin and not can_margin(user)):
		frappe.throw(_("没有此提成操作或毛利基数的授权。"), frappe.PermissionError)
	if sales_order:
		frappe.has_permission("Sales Order", "read", doc=sales_order, user=user, throw=True)


def has_permission(doc, user=None, permission_type=None, **kwargs):
	if not (can_manage(user) or can_finance(user)):
		return False
	if doc.doctype == SHEET and doc.get("basis_type") == "财务确认毛利" and not can_margin(user):
		return False
	if permission_type in {"delete", "cancel", "submit", "amend", "import"}:
		return False
	if permission_type in {"write", "create"}:
		if not (can_manage(user) if doc.doctype == SHEET else can_finance(user)):
			return False
	return not doc.get("sales_order") or frappe.has_permission("Sales Order", "read", doc=doc.sales_order, user=user)


def query_conditions(doctype, user=None):
	user = user or frappe.session.user
	if not (can_manage(user) or can_finance(user)):
		return "1=0"
	from frappe.model.db_query import DatabaseQuery
	condition = DatabaseQuery("Sales Order", user=user).build_match_conditions() or "1=1"
	result = f"`tab{doctype}`.sales_order IN (SELECT `tabSales Order`.name FROM `tabSales Order` WHERE {condition})"
	if doctype == SHEET and not can_margin(user):
		result += " AND `tabSales Commission Sheet`.basis_type != '财务确认毛利'"
	return result


def sheet_query_conditions(user=None):
	return query_conditions(SHEET, user)


def receipt_query_conditions(user=None):
	return query_conditions(RECEIPT, user)


def payment_query_conditions(user=None):
	return query_conditions(PAYMENT, user)


def own_sales_person():
	from client_akivision.utils.order_record_permissions import get_current_sales_person
	person = get_current_sales_person()
	if not person:
		frappe.throw(_("当前账号未唯一绑定有效业务人员，请联系管理员。"), frappe.PermissionError)
	return person
