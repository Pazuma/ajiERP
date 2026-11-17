from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.order_record_permissions import (
	get_order_scope_condition,
	is_scoped_user,
	permission_query_conditions,
	purchase_order_has_permission,
	sales_order_has_permission,
)
from client_akivision.utils.purchase_order_fields import set_and_validate_procurement_specialist
from client_akivision.utils.sales_order_fields import enforce_current_user_sales_person


class TestOrderRecordPermissions(FrappeTestCase):
	@patch("client_akivision.utils.order_record_permissions.frappe.get_roles")
	def test_sales_user_is_scoped_but_manager_is_not(self, get_roles):
		get_roles.return_value = ["Sales User"]
		self.assertTrue(is_scoped_user("Sales Order", "sales@example.test"))

		get_roles.return_value = ["Sales User", "Sales Manager"]
		self.assertFalse(is_scoped_user("Sales Order", "sales-manager@example.test"))

	@patch("client_akivision.utils.order_record_permissions.frappe.db.has_column", return_value=True)
	@patch("client_akivision.utils.order_record_permissions.frappe.db.escape", return_value="'sales@example.test'")
	def test_sales_scope_matches_owner_or_sales_team(self, _escape, _has_column):
		condition = get_order_scope_condition("Sales Order", "sales@example.test")
		self.assertIn("scoped_sp.name = so.custom_sales_person", condition)
		self.assertIn("tabSales Team", condition)
		self.assertIn("scoped_emp.user_id = 'sales@example.test'", condition)

	@patch("client_akivision.utils.order_record_permissions.frappe.get_roles", return_value=["Purchase User"])
	@patch("client_akivision.utils.order_record_permissions.frappe.db.has_column", return_value=True)
	@patch("client_akivision.utils.order_record_permissions.frappe.db.escape", return_value="'buyer@example.test'")
	def test_purchase_scope_uses_assigned_employee(self, _escape, _has_column, _roles):
		condition = get_order_scope_condition("Purchase Order", "buyer@example.test")
		self.assertIn("po.custom_procurement_specialist", condition)
		self.assertIn("scoped_emp.user_id = 'buyer@example.test'", condition)

	@patch("client_akivision.utils.order_record_permissions.frappe.get_roles", return_value=["Sales User"])
	@patch("client_akivision.utils.order_record_permissions.get_order_scope_condition", return_value="1=0")
	def test_unmapped_user_gets_fail_closed_list_condition(self, _scope, _roles):
		self.assertEqual(permission_query_conditions("sales@example.test", doctype="Sales Order"), "1=0")

	@patch("client_akivision.utils.order_record_permissions.frappe.get_roles", return_value=["Purchase User"])
	@patch("client_akivision.utils.order_record_permissions.get_order_scope_condition", return_value="po.custom_procurement_specialist = 'EMP-A'")
	def test_frappe_hook_call_uses_actual_table_name(self, _scope, _roles):
		condition = frappe.call(permission_query_conditions, "buyer@example.test", doctype="Purchase Order")
		self.assertEqual(condition, "`tabPurchase Order`.custom_procurement_specialist = 'EMP-A'")

	@patch("client_akivision.utils.order_record_permissions.frappe.get_roles", return_value=["Sales User"])
	@patch("client_akivision.utils.order_record_permissions.frappe.db.has_column", return_value=True)
	@patch("client_akivision.utils.order_record_permissions.frappe.db.exists", return_value=True)
	@patch("client_akivision.utils.order_record_permissions.frappe.db.escape", return_value="'sales@example.test'")
	@patch("client_akivision.utils.order_record_permissions.frappe.db.sql", return_value=[])
	def test_direct_order_read_is_denied_when_not_assigned(self, _sql, _escape, _exists, _has_column, _roles):
		self.assertFalse(
			sales_order_has_permission(
				frappe._dict(doctype="Sales Order", name="SO-OTHER"),
				"sales@example.test",
				"read",
			)
		)

	@patch("client_akivision.utils.order_record_permissions.is_scoped_user", return_value=True)
	def test_new_purchase_order_form_uses_standard_read_permission(self, _scoped):
		doc = frappe._dict(doctype="Purchase Order", name="new-purchase-order-test")
		doc.is_new = lambda: True
		self.assertTrue(purchase_order_has_permission(doc, "buyer@example.test", "read"))

	@patch("client_akivision.utils.order_record_permissions.is_scoped_user", return_value=False)
	def test_unscoped_user_hook_explicitly_allows_standard_permission_check(self, _scoped):
		self.assertTrue(purchase_order_has_permission("PO-1", "manager@example.test", "read"))

	@patch("client_akivision.utils.order_record_permissions.is_scoped_user", return_value=True)
	@patch("client_akivision.utils.order_record_permissions.get_current_sales_person", return_value="SP-A")
	def test_new_sales_order_is_assigned_to_logged_in_sales_person(self, _sales_person, _scoped):
		doc = frappe._dict(doctype="Sales Order", custom_sales_person="SP-CUSTOMER")
		doc.is_new = lambda: True
		rows = []
		doc.set = lambda fieldname, value: setattr(doc, fieldname, value)
		doc.append = lambda fieldname, row: rows.append(frappe._dict(row))
		doc.get = lambda fieldname: rows if fieldname == "sales_team" else dict.get(doc, fieldname)

		enforce_current_user_sales_person(doc)

		self.assertEqual(doc.custom_sales_person, "SP-A")
		self.assertEqual(rows, [frappe._dict(sales_person="SP-A", allocated_percentage=100)])

	@patch("client_akivision.utils.purchase_order_fields.is_scoped_user", return_value=True)
	@patch("client_akivision.utils.purchase_order_fields.get_current_employee", return_value="EMP-A")
	def test_new_purchase_order_is_assigned_to_logged_in_employee(self, _employee, _scoped):
		doc = frappe._dict(doctype="Purchase Order", custom_procurement_specialist="EMP-OTHER")
		doc.is_new = lambda: True
		doc.meta = frappe._dict(has_field=lambda fieldname: fieldname == "custom_procurement_specialist")

		set_and_validate_procurement_specialist(doc)

		self.assertEqual(doc.custom_procurement_specialist, "EMP-A")
