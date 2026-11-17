import frappe
from frappe.tests.utils import FrappeTestCase

from client_akivision.utils.stock_entry_types import (
	PURCHASE_RECEIPT_REASON,
	STOCK_ENTRY_REASON_MAP,
	apply_stock_entry_reason,
)


class TestStockEntryReasons(FrappeTestCase):
	def test_reason_sets_compatible_stock_entry_type(self):
		doc = frappe.new_doc("Stock Entry")
		doc.custom_stock_direction = "出库"
		doc.custom_stock_reason = "生产领料"

		apply_stock_entry_reason(doc)

		self.assertEqual(doc.stock_entry_type, "组装领料")

	def test_reason_rejects_wrong_direction(self):
		doc = frappe.new_doc("Stock Entry")
		doc.custom_stock_direction = "入库"
		doc.custom_stock_reason = "生产领料"

		self.assertRaises(frappe.ValidationError, apply_stock_entry_reason, doc)

	def test_purchase_receipt_reason_is_not_a_stock_entry(self):
		doc = frappe.new_doc("Stock Entry")
		doc.custom_stock_direction = "入库"
		doc.custom_stock_reason = PURCHASE_RECEIPT_REASON

		self.assertRaises(frappe.ValidationError, apply_stock_entry_reason, doc)

	def test_every_manual_reason_maps_to_a_supported_type(self):
		for reason, mapping in STOCK_ENTRY_REASON_MAP.items():
			self.assertTrue(frappe.db.exists("Stock Entry Type", mapping["stock_entry_type"]), reason)
