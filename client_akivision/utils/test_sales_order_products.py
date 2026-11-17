import json

import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.sales_order_products import (
	MAX_SUMMARY_ORDERS,
	_item_payload,
	_parse_sales_order_names,
)


class TestSalesOrderProducts(FrappeTestCase):
	def test_parse_names_deduplicates_and_preserves_order(self):
		self.assertEqual(
			_parse_sales_order_names(json.dumps(["SO-2", "SO-1", "SO-2", ""])),
			["SO-2", "SO-1"],
		)

	def test_parse_names_rejects_oversized_batches(self):
		with self.assertRaises(frappe.ValidationError):
			_parse_sales_order_names([f"SO-{index}" for index in range(MAX_SUMMARY_ORDERS + 1)])

	def test_item_payload_uses_product_name_and_uom_fallbacks(self):
		payload = _item_payload(
			frappe._dict(
				{
					"item_code": "ITEM-001",
					"item_name": "产品一",
					"description": "规格一",
					"qty": 2,
					"uom": "",
					"stock_uom": "Nos",
				}
			)
		)
		self.assertEqual(payload["item_name"], "产品一")
		self.assertEqual(payload["description"], "规格一")
		self.assertEqual(payload["uom"], "Nos")
