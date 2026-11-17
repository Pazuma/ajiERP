"""Project collaboration scope and finance-only data protection."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


FINANCE_ROLES = {"Accounts User", "Accounts Manager"}
ADMIN_ROLES = {"System Manager"}
PROJECT_COLLABORATOR_ROLES = {"Projects User"}
PROJECT_FINANCE_FIELDS = {
	"estimated_costing", "total_costing_amount", "total_purchase_cost", "total_sales_amount",
	"total_billable_amount", "total_billed_amount", "total_consumed_material_cost",
	"gross_margin", "per_gross_margin", "custom_project_budget_total", "custom_project_budget_details",
	"custom_project_cost_details", "custom_project_cost_detail_total",
}


def is_project_finance_user(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & (FINANCE_ROLES | ADMIN_ROLES))


def require_project_finance():
	if not is_project_finance_user():
		frappe.throw("仅财务人员和管理员可查看项目预算及成本信息", frappe.PermissionError)


def can_read_project(doc, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or set(frappe.get_roles(user)) & (ADMIN_ROLES | {"Projects Manager"}):
		return True
	if not doc:
		return False
	if isinstance(doc, str):
		doc = frappe.get_doc("Project", doc)
	return bool(
		frappe.db.exists("Project User", {"parent": doc.name, "parenttype": "Project", "user": user})
		or doc.get("custom_project_leader") == user
	)


def project_has_permission(doc, ptype=None, user=None):
	if not doc:
		return True
	user = user or frappe.session.user
	if ptype not in (None, "read", "select", "print", "email", "report", "export"):
		return None
	return True if can_read_project(doc, user) else False


def project_permission_query(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or set(frappe.get_roles(user)) & (ADMIN_ROLES | {"Projects Manager"}):
		return ""
	return (
		"(`tabProject`.name in (select parent from `tabProject User` "
		f"where parenttype='Project' and user={frappe.db.escape(user)}) "
		f"or `tabProject`.custom_project_leader={frappe.db.escape(user)})"
	)


def _ensure_user_source_field():
	create_custom_fields({"Project User": [{
		"fieldname": "custom_auto_assigned_by_project_node",
		"label": "由项目节点负责人自动授权",
		"fieldtype": "Check",
		"hidden": 1,
		"read_only": 1,
	}]}, update=True)
	frappe.db.updatedb("Project User")


def ensure_schema():
	"""Protect financial Project fields and track automatically-added members."""
	_ensure_user_source_field()
	for fieldname in sorted(PROJECT_FINANCE_FIELDS):
		if frappe.get_meta("Project").has_field(fieldname):
			make_property_setter("Project", fieldname, "permlevel", 9, "Int", validate_fields_for_doctype=False)
	# Frappe field-level permissions hide these values from users without level 9.
	custom_finance_fields = [
		{"fieldname": fieldname, "permlevel": 9}
		for fieldname in PROJECT_FINANCE_FIELDS
		if frappe.get_meta("Project").has_field(fieldname)
			and frappe.db.exists("Custom Field", {"dt": "Project", "fieldname": fieldname})
	]
	if custom_finance_fields:
		create_custom_fields({"Project": custom_finance_fields}, update=True)
	project_meta = frappe.get_doc("DocType", "Project")
	for role in sorted(PROJECT_COLLABORATOR_ROLES):
		if not frappe.db.exists("Role", role):
			continue
		permission = next((row for row in project_meta.permissions if row.role == role and row.permlevel == 0), None)
		if not permission:
			permission = project_meta.append("permissions", {"role": role, "permlevel": 0, "read": 1})
		else:
			permission.read = 1
			permission.write = 0
			permission.create = 0
			permission.delete = 0
			permission.submit = 0
			permission.cancel = 0
			permission.amend = 0
	for role in sorted(FINANCE_ROLES):
		if not frappe.db.exists("Role", role):
			continue
		base_permission = next((row for row in project_meta.permissions if row.role == role and row.permlevel == 0), None)
		if not base_permission:
			project_meta.append("permissions", {"role": role, "permlevel": 0, "read": 1})
		else:
			base_permission.read = 1
		permission = next((row for row in project_meta.permissions if row.role == role and row.permlevel == 9), None)
		if not permission:
			permission = project_meta.append("permissions", {"role": role, "permlevel": 9, "read": 1})
		else:
			permission.read = 1
	project_meta.save(ignore_permissions=True)
	for report_name, roles in {
		"Project wise Stock Tracking": FINANCE_ROLES,
		"Timesheet Billing Summary": FINANCE_ROLES,
		# The standard report ignores Project query permissions; keep its broad
		# aggregation limited to project administrators.
		"Project Summary": {"Projects Manager"},
	}.items():
		if not frappe.db.exists("Report", report_name):
			continue
		report = frappe.get_doc("Report", report_name)
		if report.report_type != "Script Report":
			continue
		current_roles = {row.role for row in report.roles}
		if current_roles != roles:
			frappe.db.delete("Has Role", {"parent": report_name, "parenttype": "Report", "parentfield": "roles"})
			for role in sorted(roles):
				if frappe.db.exists("Role", role):
					frappe.get_doc({
						"doctype": "Has Role",
						"parent": report_name,
						"parenttype": "Report",
						"parentfield": "roles",
						"role": role,
					}).db_insert()
			frappe.db.set_value("Report", report_name, "modified", frappe.utils.now())
			frappe.clear_cache(doctype="Report")
	frappe.db.updatedb("Project")
	frappe.clear_cache(doctype="Project")
	frappe.clear_cache(doctype="Project User")


def _sync_auto_members(doc, method=None):
	if doc.is_new():
		return
	previous = doc.get_doc_before_save()
	old_users = {r.responsible_user for r in (previous.get("custom_project_progress_items") or []) if r.responsible_user} if previous else set()
	new_users = {r.responsible_user for r in (doc.get("custom_project_progress_items") or []) if r.responsible_user}
	for user in new_users - old_users:
		if not frappe.db.exists("Project User", {"parent": doc.name, "parenttype": "Project", "user": user}):
			frappe.get_doc({"doctype": "Project User", "parent": doc.name, "parenttype": "Project", "parentfield": "users", "user": user, "custom_auto_assigned_by_project_node": 1}).insert(ignore_permissions=True)
		frappe.clear_cache(user=user)
	for user in old_users - new_users:
		if user == doc.get("custom_project_leader"):
			continue
		if any(r.responsible_user == user for r in doc.get("custom_project_progress_items") or []):
			continue
		name = frappe.db.get_value("Project User", {"parent": doc.name, "parenttype": "Project", "user": user, "custom_auto_assigned_by_project_node": 1}, "name")
		if name:
			frappe.delete_doc("Project User", name, ignore_permissions=True)
			frappe.clear_cache(user=user)


def validate_project_finance_access(doc, method=None):
	"""Reject direct financial edits and preserve existing values on ordinary saves."""
	if is_project_finance_user():
		return
	old = doc.get_doc_before_save()
	if not old:
		for fieldname in PROJECT_FINANCE_FIELDS:
			if doc.get(fieldname):
				frappe.throw("仅财务人员和管理员可填写项目预算及成本信息", frappe.PermissionError)
		return
	for fieldname in PROJECT_FINANCE_FIELDS:
		if fieldname not in doc.meta.get_valid_columns():
			continue
		if doc.get(fieldname) != old.get(fieldname):
			frappe.throw("仅财务人员和管理员可修改项目预算及成本信息", frappe.PermissionError)


def filter_project_print_fields(doc, method=None):
	"""Keep standard Project print formats from bypassing field-level reads."""
	if is_project_finance_user():
		return
	for fieldname in PROJECT_FINANCE_FIELDS:
		if hasattr(doc, fieldname):
			delattr(doc, fieldname)

