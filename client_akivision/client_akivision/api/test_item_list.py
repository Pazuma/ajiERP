import frappe
from types import SimpleNamespace
from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase

from client_akivision.client_akivision.api.item_list import get_item_list_stock_context


class TestItemListContext(FrappeTestCase):
	@patch("client_akivision.client_akivision.api.item_list.frappe")
	def test_stock_queries_are_restricted_to_authorized_warehouses(self, mock_frappe):
		mock_frappe.parse_json.return_value = ["PRODUCT-1"]
		mock_frappe.has_permission.return_value = True
		mock_frappe.get_list.side_effect = [
			[SimpleNamespace(name="PRODUCT-1", stock_uom="Nos")],
			["Allowed - TC"], [], [],
		]
		get_item_list_stock_context(["PRODUCT-1"])
		self.assertEqual(mock_frappe.get_list.call_args_list[2].kwargs["filters"]["warehouse"], ["in", ["Allowed - TC"]])
		self.assertEqual(mock_frappe.get_list.call_args_list[3].kwargs["filters"]["warehouse"], ["in", ["Allowed - TC"]])

	def test_context_returns_structured_stock_and_reorder_rows(self):
		item = frappe.db.get_value(
			"Item", {"item_name": "螺丝"}, ["name", "stock_uom"], as_dict=True
		)
		if not item:
			self.skipTest("Test site has no screw item")

		result = get_item_list_stock_context([item.name])
		row = result["items"][item.name]
		self.assertEqual(row["stock_uom"], item.stock_uom)
		self.assertIsInstance(row["warehouses"], list)
		self.assertIsInstance(row["reorder_levels"], list)

	def test_empty_request_is_safe(self):
		self.assertEqual(get_item_list_stock_context([]), {"items": {}})
