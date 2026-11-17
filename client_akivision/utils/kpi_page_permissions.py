"""Access rules for restricted pages in the KPI dashboard sidebar."""

import frappe
from frappe import _


PROJECT_TIMEOUT_VIEWER_ROLE = "项目节点超时表查看者"
BUSINESS_FORM_OVERVIEW_VIEWER_ROLE = "业务表单总表查看者"
MANAGER_ROLES = {"System Manager"}


def _has_access(required_role, user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)) & (MANAGER_ROLES | {required_role}))


def can_view_project_timeout(user=None):
	return _has_access(PROJECT_TIMEOUT_VIEWER_ROLE, user)


def check_project_timeout_access(user=None):
	if not can_view_project_timeout(user):
		frappe.throw(_("您没有查看项目节点超时表的权限。"), frappe.PermissionError)


def can_view_business_form_overview(user=None):
	return _has_access(BUSINESS_FORM_OVERVIEW_VIEWER_ROLE, user)


def check_business_form_overview_access(user=None):
	if not can_view_business_form_overview(user):
		frappe.throw(_("您没有查看业务表单总表的权限。"), frappe.PermissionError)
