import unittest
from unittest.mock import patch

import frappe

from client_akivision.overrides.purchase_receipt import validate_return_quality_sources


class TestPurchaseReturnQuality(unittest.TestCase):
	def setUp(self):
		self.original = frappe._dict(name="PR", doctype="Purchase Receipt", docstatus=1,
			is_return=0, items=[frappe._dict(name="PR-ROW", item_code="SECOND", quality_inspection="QI")])
		self.qi = frappe._dict(docstatus=1, reference_type="Purchase Receipt", reference_name="PR",
			item_code="FIRST", status="Accepted")
		self.row = frappe._dict(idx=1, item_code="SECOND", purchase_receipt_item="PR-ROW", quality_inspection="QI")
		self.doc = frappe._dict(return_against="PR", items=[self.row])

	def validate(self):
		with patch("client_akivision.overrides.purchase_receipt.frappe") as mock:
			mock.get_doc.side_effect = [self.original, self.qi]
			mock.throw.side_effect = ValueError
			validate_return_quality_sources(self.doc)

	def test_return_uses_original_multi_item_inspection(self):
		self.validate()

	def test_invalid_lineage_fails(self):
		for target, field, value in [
			(self.original, "docstatus", 2), (self.original, "is_return", 1),
			(self.row, "purchase_receipt_item", "OTHER-ROW"),
			(self.row, "item_code", "OTHER"), (self.row, "quality_inspection", "OTHER-QI"),
			(self.qi, "docstatus", 2), (self.qi, "reference_name", "OTHER-PR"),
		]:
			with self.subTest(field=field, value=value):
				old = target[field]
				target[field] = value
				with self.assertRaises(ValueError):
					self.validate()
				target[field] = old
