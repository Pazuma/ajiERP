import unittest
from unittest.mock import patch

import frappe

from client_akivision.utils.project_permissions import (
	can_read_project,
	is_project_finance_user,
	project_has_permission,
	validate_project_finance_access,
)


class TestProjectPermissions(unittest.TestCase):
	def test_only_finance_and_admin_roles_are_finance_users(self):
		with patch("client_akivision.utils.project_permissions.frappe.get_roles", return_value=["Accounts User"]):
			self.assertTrue(is_project_finance_user("finance@example.com"))
		with patch("client_akivision.utils.project_permissions.frappe.get_roles", return_value=["Projects Manager"]):
			self.assertFalse(is_project_finance_user("manager@example.com"))

	def test_project_read_is_limited_to_project_members_and_leader(self):
		project = frappe._dict(name="PROJ-1", custom_project_leader="leader@example.com")
		with patch("client_akivision.utils.project_permissions.frappe.get_roles", return_value=["Projects User"]), patch(
			"client_akivision.utils.project_permissions.frappe.db.exists", return_value=False
		):
			self.assertTrue(can_read_project(project, "leader@example.com"))
			self.assertFalse(can_read_project(project, "outsider@example.com"))
			self.assertFalse(project_has_permission(project, "read", "outsider@example.com"))

	def test_non_finance_cannot_change_financial_values(self):
		old = frappe._dict(estimated_costing=100, custom_project_budget_total=100)
		doc = frappe._dict(
			name="PROJ-1",
			estimated_costing=200,
			custom_project_budget_total=100,
			meta=frappe._dict(get_valid_columns=lambda: ["estimated_costing", "custom_project_budget_total"]),
			get_doc_before_save=lambda: old,
		)
		with patch("client_akivision.utils.project_permissions.is_project_finance_user", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				validate_project_finance_access(doc)


def run_checks():
	suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestProjectPermissions)
	result = unittest.TextTestRunner(verbosity=2).run(suite)
	if not result.wasSuccessful():
		raise AssertionError("项目权限隔离检查失败")
	return {"tests": result.testsRun, "success": True}
