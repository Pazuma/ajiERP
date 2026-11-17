"""Finance-only sales-order accounting capabilities; never grant order access."""

import frappe
from frappe import _


EDITOR_ROLES = {"Sales Order Finance Editor", "Accounts User", "Accounts Manager", "China Finance Manager", "China Finance User", "System Manager"}
READER_ROLES = EDITOR_ROLES | {"Sales Order Finance Reader", "China Finance Auditor"}


def can_read_finance(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(READER_ROLES.intersection(frappe.get_roles(user)))


def can_edit_finance(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(EDITOR_ROLES.intersection(frappe.get_roles(user)))


def assert_finance_access(sales_order=None, action="read", user=None):
	user = user or frappe.session.user
	allowed = can_edit_finance(user) if action == "write" else can_read_finance(user)
	if not allowed:
		frappe.throw(_("仅授权财务人员可访问销售订单财务核算。"), frappe.PermissionError)
	if sales_order:
		frappe.has_permission("Sales Order", "read", doc=frappe.get_doc("Sales Order", sales_order), user=user, throw=True)


def accounting_has_permission(doc, user=None, permission_type=None, **kwargs):
	if not can_read_finance(user):
		return False
	if permission_type in {"write", "create", "delete", "submit", "cancel"} and not can_edit_finance(user):
		return False
	if doc.get("sales_order"):
		return frappe.has_permission("Sales Order", "read", doc=doc.sales_order, user=user) and (
			not doc.get("sales_invoice") or frappe.has_permission("Sales Invoice", "read", doc=doc.sales_invoice, user=user)
		)
	return permission_type == "create" and can_edit_finance(user)


def accounting_query_conditions(user=None):
	if not can_read_finance(user):
		return "1=0"
	# Reuse the framework's order user permissions, shares and custom scope hooks.
	from frappe.model.db_query import DatabaseQuery
	query = DatabaseQuery("Sales Order", user=user or frappe.session.user)
	condition = query.build_match_conditions() or "1=1"
	invoice_query = DatabaseQuery("Sales Invoice", user=user or frappe.session.user)
	invoice_condition = invoice_query.build_match_conditions() or "1=1"
	return (f"`tabSales Order Finance Accounting`.sales_order IN (SELECT `tabSales Order`.name FROM `tabSales Order` WHERE {condition})"
		f" AND `tabSales Order Finance Accounting`.sales_invoice IN (SELECT `tabSales Invoice`.name FROM `tabSales Invoice` WHERE {invoice_condition})")
