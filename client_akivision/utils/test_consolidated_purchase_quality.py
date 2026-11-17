import unittest
from unittest.mock import patch
import frappe
from client_akivision.overrides.purchase_receipt import QualityCheckedPurchaseReceipt


class TestConsolidatedPurchaseQuality(unittest.TestCase):
	def setUp(self):
		self.qi = frappe._dict(name="QI", item_code="FIRST", reference_type="Purchase Receipt",
			reference_name="PR", docstatus=1, status="Accepted", custom_purchase_order="PO",
			custom_receiving_notice="RN", custom_purchase_quality_items=[
				frappe._dict(item_code="SECOND", purchase_order_item="PO-ROW", accepted_qty=2)])
		self.row = frappe._dict(idx=2, item_code="SECOND", purchase_order="PO",
			purchase_order_item="PO-ROW", quality_inspection="QI", qty=2)
		self.doc = frappe._dict(name="PR", doctype="Purchase Receipt", custom_receiving_notice="RN",
			items=[self.row], is_return=0)

	def validate(self, previous=0):
		with patch("client_akivision.overrides.purchase_receipt.frappe") as mock:
			mock.get_doc.return_value = self.qi
			mock.db.sql.return_value = [(previous,)]
			mock.throw.side_effect = ValueError
			QualityCheckedPurchaseReceipt.validate_items_quality_inspection(self.doc)

	def test_second_item_passes(self):
		self.validate()

	def test_invalid_sources_and_quantity_fail(self):
		for target, field, value in [(self.row, "item_code", "OTHER"),
			(self.row, "purchase_order_item", "OTHER"), (self.row, "purchase_order", "OTHER"),
			(self.doc, "custom_receiving_notice", "OTHER"), (self.qi, "docstatus", 0),
			(self.qi, "status", "Rejected"), (self.row, "qty", 3)]:
			with self.subTest(field=field):
				original = target[field]
				target[field] = value
				with self.assertRaises(ValueError):
					self.validate()
				target[field] = original

	def test_duplicate_rows_exceed_limit(self):
		self.doc.get("items").append(frappe._dict(self.row))
		with self.assertRaises(ValueError):
			self.validate()

	def test_other_receipt_reserves_quantity(self):
		with self.assertRaises(ValueError):
			self.validate(previous=1)

	def test_rejected_quantity_requires_warehouse_and_respects_limit(self):
		self.qi.custom_purchase_quality_items[0].rejected_qty = 1
		self.row.rejected_qty = 1
		with self.assertRaises(ValueError):
			self.validate()
		self.row.rejected_warehouse = "Rejected Warehouse"
		self.validate()
		self.row.rejected_qty = 2
		with self.assertRaises(ValueError):
			self.validate()

	def test_entirely_rejected_receipt(self):
		self.qi.status = "Rejected"
		self.qi.custom_purchase_quality_items[0].accepted_qty = 0
		self.qi.custom_purchase_quality_items[0].rejected_qty = 2
		self.row.qty = 0
		self.row.rejected_qty = 2
		self.row.rejected_warehouse = "Rejected Warehouse"
		self.validate()

	def test_other_receipt_reserves_rejected_quantity(self):
		self.qi.custom_purchase_quality_items[0].rejected_qty = 1
		self.row.qty = 0
		self.row.rejected_qty = 1
		self.row.rejected_warehouse = "Rejected Warehouse"
		with self.assertRaises(ValueError):
			self.validate(previous=1)

	def test_standard_single_item_rule(self):
		self.qi.custom_purchase_quality_items = []
		with self.assertRaises(ValueError):
			self.validate()
		self.row.item_code = "FIRST"
		self.validate()
