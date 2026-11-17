from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.item_product_identity import (
	create_sales_product,
	update_sales_product,
	get_sales_products,
	ensure_sales_product_permissions,
	sales_item_has_permission,
	sales_item_query_conditions,
)
from client_akivision.utils.sales_product_field_permissions import ensure_schema


class TestSalesProductNativeList(FrappeTestCase):
	def test_sales_editor_can_create_and_update_item_price(self):
		ensure_sales_product_permissions()
		user = "product-price-" + uuid4().hex[:12] + "@example.test"
		frappe.get_doc({"doctype": "User", "email": user, "first_name": "Product price",
			"send_welcome_email": 0, "roles": [{"role": "Sales User"}]}).insert(ignore_permissions=True)
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		uom = frappe.db.get_value("UOM", {}, "name")
		price_list = frappe.db.get_value("Price List", {"enabled": 1, "selling": 1, "buying": 0}, "name")
		if not price_list or not group or not uom:
			self.skipTest("Sales price list, item group and UOM are required")
		code = "TEST-EDIT-PRICE-" + uuid4().hex[:12]
		original_user = frappe.session.user
		try:
			frappe.set_user(user)
			create_sales_product(code, "Priced product", group, uom,
				custom_internal_model=code + "-internal", custom_external_model=code + "-external")
			args = dict(item_code=code, item_name="Priced product", item_group=group, stock_uom=uom)
			update_sales_product(**args, price_list=price_list, price=125)
			prices = frappe.get_all("Item Price", filters={"item_code": code, "price_list": price_list},
				fields=["name", "price_list_rate"])
			self.assertEqual(len(prices), 1)
			self.assertEqual(prices[0].price_list_rate, 125)
			update_sales_product(**args, price_list=price_list, price=150, price_name=prices[0].name)
			self.assertEqual(frappe.db.get_value("Item Price", prices[0].name, "price_list_rate"), 150)
			with self.assertRaises(frappe.ValidationError):
				update_sales_product(**args, price_list="invalid-price-list", price=200)
			self.assertEqual(frappe.db.get_value("Item Price", prices[0].name, "price_list_rate"), 150)
		finally:
			frappe.set_user(original_user)

	@patch("erpnext.stock.get_item_details.get_item_details")
	@patch("client_akivision.api.sales_product_item_details._sales_only_user", return_value=True)
	@patch("frappe.has_permission", return_value=True)
	def test_sales_order_item_details_preserve_price_and_quantity_only(self, has_permission, sales_only, native):
		from client_akivision.api.sales_product_item_details import get_item_details
		native.return_value = frappe._dict(rate=123, actual_qty=5, valuation_rate=30, last_purchase_rate=20, gross_profit=93)
		result = get_item_details({"doctype": "Sales Order", "item_code": "PRODUCT"})
		self.assertEqual(result["rate"], 123)
		self.assertEqual(result["actual_qty"], 5)
		self.assertNotIn("valuation_rate", result)
		self.assertNotIn("last_purchase_rate", result)
		self.assertNotIn("gross_profit", result)

	@patch("erpnext.stock.utils.get_stock_balance")
	@patch("client_akivision.api.sales_product_item_details._sales_only_user", return_value=True)
	@patch("frappe.has_permission", return_value=True)
	def test_sales_stock_balance_refuses_valuation(self, has_permission, sales_only, native):
		from client_akivision.api.sales_product_item_details import get_stock_balance
		with self.assertRaises(frappe.PermissionError):
			get_stock_balance("PRODUCT", "WAREHOUSE", with_valuation_rate=True)
		native.assert_not_called()
		native.return_value = 5
		self.assertEqual(get_stock_balance("PRODUCT", "WAREHOUSE"), 5)

	@patch("erpnext.stock.get_item_details.get_item_details")
	@patch("client_akivision.api.sales_product_item_details._sales_only_user", return_value=False)
	def test_other_roles_keep_original_item_details(self, sales_only, native):
		from client_akivision.api.sales_product_item_details import get_item_details
		native.return_value = frappe._dict(rate=123, valuation_rate=30)
		self.assertEqual(get_item_details({"doctype": "Purchase Order", "item_code": "PRODUCT"}), native.return_value)

	def test_real_sales_role_can_create_but_cannot_read_cost_fields(self):
		from frappe.model import get_permitted_fields
		ensure_sales_product_permissions()
		ensure_schema()
		user = "product-test-" + uuid4().hex[:12] + "@example.test"
		frappe.get_doc({"doctype": "User", "email": user, "first_name": "Product test",
			"send_welcome_email": 0, "roles": [{"role": "Sales User"}]}).insert(ignore_permissions=True)
		original_user = frappe.session.user
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		uom = frappe.db.get_value("UOM", {}, "name")
		price_list = frappe.db.get_value("Price List", {"enabled": 1, "selling": 1, "buying": 0}, "name")
		code = "TEST-REAL-SALES-" + uuid4().hex[:12]
		try:
			frappe.set_user(user)
			self.assertTrue(frappe.has_permission("Item", "create"))
			for doctype, fields in (("Item", ["valuation_rate", "last_purchase_rate"]), ("Bin", ["valuation_rate", "stock_value"]), ("Sales Order", ["custom_production_cost", "custom_gross_profit"])):
				permitted = get_permitted_fields(doctype, user=user)
				for field in fields:
					self.assertNotIn(field, permitted)
			created = create_sales_product(code, "Real role product", group, uom,
				custom_internal_model=code + "-internal", custom_external_model=code + "-external",
				price_list=price_list, price=123 if price_list else None,
				description="Detailed specification", image="/files/product-test.png")
			self.assertEqual(created["item_code"], code)
			self.assertEqual(frappe.db.get_value("Item", code, "description"), "Detailed specification")
			self.assertEqual(frappe.db.get_value("Item", code, "image"), "/files/product-test.png")
			if price_list:
				prices = frappe.get_list("Item Price", filters={"item_code": code}, fields=["price_list_rate"])
				self.assertEqual(len(prices), 1)
				self.assertEqual(prices[0].price_list_rate, 123)
			from client_akivision.client_akivision.api.item_list import get_item_list_stock_context
			stock = get_item_list_stock_context([code], include_zero_qty=1, view="sales_product")
			self.assertEqual(stock["items"][code]["stock_uom"], uom)
			self.assertEqual(stock["items"][code]["warehouses"], [])
			from client_akivision.api.sales_product_item_details import get_item_master_details, get_valuation_rate
			self.assertNotIn("valuation_rate", get_item_master_details(code))
			with self.assertRaises(frappe.PermissionError):
				get_valuation_rate(code, "unused")
		finally:
			frappe.set_user(original_user)

	def test_invalid_sales_price_does_not_leave_an_item(self):
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		uom = frappe.db.get_value("UOM", {}, "name")
		code = "TEST-INVALID-PRICE-" + uuid4().hex[:12]
		with self.assertRaises(frappe.ValidationError):
			create_sales_product(code, "Invalid price product", group, uom,
				custom_internal_model=code + "-internal", custom_external_model=code + "-external",
				price_list="invalid-price-list", price=-1)
		self.assertFalse(frappe.db.exists("Item", code))

	def test_new_product_is_the_same_item_in_both_lists(self):
		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		uom = frappe.db.get_value("UOM", {}, "name")
		if not group or not uom:
			self.skipTest("Item Group and UOM fixtures are required")
		code = "TEST-SALES-PRODUCT-" + uuid4().hex[:12]
		created = create_sales_product(
			code, "Sales product test", group, uom,
			custom_internal_model=code + "-internal",
			custom_external_model=code + "-external",
		)
		self.assertEqual(created["item_code"], code)
		self.assertEqual(frappe.db.get_value("Item", code, "is_sales_item"), 1)
		self.assertEqual(frappe.get_list("Item", filters={"name": code}, pluck="name"), [code])
		self.assertIn(code, [row.item_code for row in get_sales_products(search=code)])

	@patch("frappe.get_roles", return_value=["Sales User"])
	def test_sales_only_user_cannot_remove_sales_filter(self, get_roles):
		self.assertIn("`tabItem`.`is_sales_item` = 1", sales_item_query_conditions("sales@example.test"))
		self.assertIn("`tabItem`.`disabled` = 0", sales_item_query_conditions("sales@example.test"))
		self.assertFalse(sales_item_has_permission(frappe._dict(is_sales_item=0, disabled=0), ptype="read", user="sales@example.test"))
		self.assertFalse(sales_item_has_permission(frappe._dict(is_sales_item=1, disabled=1), ptype="read", user="sales@example.test"))
		self.assertTrue(sales_item_has_permission(frappe._dict(is_sales_item=1, disabled=0), ptype="read", user="sales@example.test"))
		self.assertFalse(sales_item_has_permission(frappe._dict(is_sales_item=0, disabled=0), ptype="write", user="sales@example.test"))

	@patch("frappe.get_roles", return_value=["Sales User", "Stock User"])
	def test_stock_sales_user_keeps_existing_item_access(self, get_roles):
		self.assertEqual(sales_item_query_conditions("stock@example.test"), "")
		self.assertTrue(sales_item_has_permission(frappe._dict(is_sales_item=0, disabled=0), ptype="read", user="stock@example.test"))
