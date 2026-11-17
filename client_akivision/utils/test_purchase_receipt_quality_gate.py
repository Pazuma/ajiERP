import unittest
from unittest.mock import patch

import frappe

from client_akivision.utils.purchase_receipt import validate_purchase_receipt_gate


class TestPurchaseReceiptQualityGate(unittest.TestCase):
	@patch("client_akivision.utils.purchase_receipt.frappe")
	def test_requires_purchase_order(self, frappe_mock):
		doc = frappe._dict(items=[frappe._dict(idx=1, purchase_order=None)], is_return=0, docstatus=1)
		frappe_mock.throw.side_effect = RuntimeError
		with self.assertRaises(RuntimeError):
			validate_purchase_receipt_gate(doc)

	@patch("client_akivision.utils.purchase_receipt.frappe")
	def test_rejected_quality_inspection_blocks_receipt(self, frappe_mock):
		doc = frappe._dict(
			name="PR-1",
			items=[frappe._dict(idx=1, item_code="ITEM-1", purchase_order="PO-1", quality_inspection="QI-1")],
			is_return=0,
			docstatus=1,
		)
		frappe_mock.db.get_value.side_effect = [
			frappe._dict(docstatus=1, status="To Receive"),
			frappe._dict(docstatus=1, status="Rejected", reference_type="Purchase Receipt", reference_name="PR-1"),
		]
		frappe_mock.throw.side_effect = RuntimeError
		with self.assertRaises(RuntimeError):
			validate_purchase_receipt_gate(doc)

	@patch("client_akivision.utils.purchase_receipt.frappe")
	def test_accepted_inspection_for_current_receipt_passes(self, frappe_mock):
		doc = frappe._dict(
			name="PR-1",
			items=[frappe._dict(idx=1, item_code="ITEM-1", purchase_order="PO-1", quality_inspection="QI-1")],
			is_return=0,
			docstatus=1,
		)
		frappe_mock.db.get_value.side_effect = [
			frappe._dict(docstatus=1, status="To Receive"),
			frappe._dict(docstatus=1, status="Accepted", reference_type="Purchase Receipt", reference_name="PR-1"),
		]
		validate_purchase_receipt_gate(doc)
		frappe_mock.throw.assert_not_called()


if __name__ == "__main__":
	unittest.main()
