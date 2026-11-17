from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.kpi_page_permissions import (
	BUSINESS_FORM_OVERVIEW_VIEWER_ROLE,
	PROJECT_TIMEOUT_VIEWER_ROLE,
	can_view_business_form_overview,
	can_view_project_timeout,
)
from client_akivision.utils.workspace_sidebar import _filter_restricted_kpi_links


class TestKPIPagePermissions(FrappeTestCase):
	@patch("client_akivision.utils.kpi_page_permissions.frappe.get_roles")
	def test_restricted_roles_are_independent(self, get_roles):
		get_roles.return_value = [PROJECT_TIMEOUT_VIEWER_ROLE]
		self.assertTrue(can_view_project_timeout("test@example.com"))
		self.assertFalse(can_view_business_form_overview("test@example.com"))

		get_roles.return_value = [BUSINESS_FORM_OVERVIEW_VIEWER_ROLE]
		self.assertFalse(can_view_project_timeout("test@example.com"))
		self.assertTrue(can_view_business_form_overview("test@example.com"))

	@patch("client_akivision.utils.kpi_page_permissions.frappe.get_roles")
	def test_system_manager_can_view_both_pages(self, get_roles):
		get_roles.return_value = ["System Manager"]
		self.assertTrue(can_view_project_timeout("manager@example.com"))
		self.assertTrue(can_view_business_form_overview("manager@example.com"))

	def test_administrator_can_view_both_pages(self):
		self.assertTrue(can_view_project_timeout("Administrator"))
		self.assertTrue(can_view_business_form_overview("Administrator"))

	def test_sidebar_filter_only_removes_restricted_links(self):
		items = [
			frappe._dict(link_to="operations-kpi-dashboard"),
			frappe._dict(link_to="project-progress-timeout"),
			frappe._dict(link_to="business-form-overview"),
			frappe._dict(link_to="KPI Target"),
		]
		_filter_restricted_kpi_links(items, allow_timeout=True, allow_overview=False)
		self.assertEqual(
			[item.link_to for item in items],
			["operations-kpi-dashboard", "project-progress-timeout", "KPI Target"],
		)

	def test_restricted_role_only_sees_its_authorized_page(self):
		items = [
			frappe._dict(link_to="operations-kpi-dashboard"),
			frappe._dict(link_to="project-progress-timeout"),
			frappe._dict(link_to="business-form-overview"),
			frappe._dict(link_to="KPI Target"),
		]
		_filter_restricted_kpi_links(
			items, allow_timeout=False, allow_overview=True, has_base_access=False
		)
		self.assertEqual([item.link_to for item in items], ["business-form-overview"])
