"""Record-level visibility for Sales User and Purchase User accounts."""

import re

import frappe


SCOPE_ROLES = {
	"Sales Order": ("Sales User", "Sales Manager"),
	"Purchase Order": ("Purchase User", "Purchase Manager"),
}
OWNER_FIELDS = {
	"Sales Order": "custom_sales_person",
	"Purchase Order": "custom_procurement_specialist",
}


def _user(user=None):
	return user or frappe.session.user


def is_scoped_user(doctype, user=None):
	"""Return whether the user is an individual business user for this order type."""
	user = _user(user)
	if doctype not in SCOPE_ROLES or user in ("Administrator", "Guest"):
		return False
	roles = set(frappe.get_roles(user))
	user_role, manager_role = SCOPE_ROLES[doctype]
	return user_role in roles and manager_role not in roles and "System Manager" not in roles


def _validated_alias(alias):
	if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias or ""):
		frappe.throw("Invalid SQL table alias")
	return alias


def get_order_scope_condition(doctype, user=None, alias=None):
	"""Return a SQL predicate for an individual business user's order rows."""
	if doctype not in OWNER_FIELDS:
		frappe.throw(f"Unsupported order type: {doctype}")
	user = _user(user)
	alias = _validated_alias(alias or ("so" if doctype == "Sales Order" else "po"))
	if user in ("Administrator", "Guest"):
		return "1=1"

	if doctype == "Sales Order":
		if not frappe.db.has_column(doctype, "custom_sales_person"):
			return "1=0"
		user_sql = frappe.db.escape(user)
		return f"""EXISTS (
			SELECT 1
			FROM `tabSales Person` scoped_sp
			INNER JOIN `tabEmployee` scoped_emp ON scoped_emp.name = scoped_sp.employee
			WHERE scoped_emp.user_id = {user_sql}
			  AND scoped_emp.status = 'Active'
			  AND scoped_sp.enabled = 1
			  AND scoped_sp.is_group = 0
			  AND (
				scoped_sp.name = {alias}.custom_sales_person
				OR EXISTS (
					SELECT 1 FROM `tabSales Team` scoped_team
					WHERE scoped_team.parent = {alias}.name
					  AND scoped_team.sales_person = scoped_sp.name
				)
			  )
		)"""

	if not frappe.db.has_column(doctype, "custom_procurement_specialist"):
		return "1=0"
	user_sql = frappe.db.escape(user)
	return f"""EXISTS (
		SELECT 1 FROM `tabEmployee` scoped_emp
		WHERE scoped_emp.name = {alias}.custom_procurement_specialist
		  AND scoped_emp.user_id = {user_sql}
		  AND scoped_emp.status = 'Active'
	)"""


def permission_query_conditions(user=None, doctype=None):
	"""Frappe list-query hook. Non-individual roles keep standard DocType scope."""
	user = _user(user)
	if not is_scoped_user(doctype, user):
		return None
	condition = get_order_scope_condition(doctype, user)
	alias = "so" if doctype == "Sales Order" else "po"
	return condition.replace(f"{alias}.", f"`tab{doctype}`.")


def _document_matches(doctype, doc, user):
	if isinstance(doc, str):
		doc = frappe.get_doc(doctype, doc)
	if not doc or not doc.get("name"):
		return False
	alias = "so" if doctype == "Sales Order" else "po"
	condition = get_order_scope_condition(doctype, user, alias)
	return bool(
		frappe.db.sql(
			f"SELECT 1 FROM `tab{doctype}` {alias} WHERE {alias}.name = %s AND ({condition}) LIMIT 1",
			(doc.name,),
		)
	)


def sales_order_has_permission(doc, user=None, permission_type=None):
	return _has_order_permission("Sales Order", doc, user, permission_type)


def purchase_order_has_permission(doc, user=None, permission_type=None):
	return _has_order_permission("Purchase Order", doc, user, permission_type)


def _has_order_permission(doctype, doc, user=None, permission_type=None):
	user = _user(user)
	if not is_scoped_user(doctype, user):
		return True
	if permission_type == "create":
		return True
	# New form documents have a temporary name but no owner row in the database.
	# Let the DocType's standard permission decide whether the user may open/create
	# the form; the before-validate hooks enforce ownership when it is saved.
	docname = doc if isinstance(doc, str) else (doc.get("name") if doc else None)
	is_new = getattr(doc, "is_new", None) if not isinstance(doc, str) else None
	if (callable(is_new) and is_new()) or (docname and not frappe.db.exists(doctype, docname)):
		return True
	return _document_matches(doctype, doc, user)


def get_current_employee(user=None):
	"""Return the unique active Employee mapped to a login, or None if ambiguous."""
	user = _user(user)
	rows = frappe.get_all(
		"Employee",
		filters={"user_id": user, "status": "Active"},
		pluck="name",
		limit_page_length=0,
	)
	return rows[0] if len(rows) == 1 else None


def get_current_sales_person(user=None):
	"""Return the unique enabled leaf Sales Person for a login, or None."""
	employee = get_current_employee(user)
	if not employee:
		return None
	rows = frappe.get_all(
		"Sales Person",
		filters={"employee": employee, "enabled": 1, "is_group": 0},
		pluck="name",
		limit_page_length=0,
	)
	return rows[0] if len(rows) == 1 else None
