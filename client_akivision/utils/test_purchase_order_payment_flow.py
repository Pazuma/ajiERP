import unittest
from unittest.mock import patch
import frappe
from client_akivision.utils.purchase_order_payment_flow import _recalculate, validate_invoice_reconciliation


class TestPurchaseOrderPaymentFlow(unittest.TestCase):
	def test_completion_requires_all_stages(self):
		cases = [
			(50, 0, [1], [], "待收货"),
			(100, 100, [1, 0], [0], "待对账"),
			(100, 50, [1], [0], "待开票"),
			(100, 100, [1], [10], "待付款"),
			(100, 100, [1], [0], "已完成"),
			(100, 100, [1], [10, -10], "待付款"),
			(100, 100, [], [0], "待对账"),
		]
		for received, billed, reconciled, balances, expected in cases:
			with self.subTest(expected=expected), patch("client_akivision.utils.purchase_order_payment_flow.frappe") as mock:
				mock.get_doc.return_value = frappe._dict(docstatus=1, per_received=received, per_billed=billed)
				mock.db.sql.side_effect = [
					[frappe._dict(reconciled=r) for r in reconciled],
					[frappe._dict(grand_total=100, outstanding_amount=b) for b in balances]]
				_recalculate("PO")
				self.assertEqual(mock.db.set_value.call_args.args[2]["custom_procurement_flow_status"], expected)

	def test_invoice_requires_confirmed_matching_receipt(self):
		row = frappe._dict(idx=1, purchase_order="PO", po_detail="POI", purchase_receipt="PR",
			pr_detail="PRI", item_code="ITEM")
		doc = frappe._dict(items=[row], company="C", supplier="S", currency="CNY")
		for confirmed in [[], ["RECON"]]:
			with patch("client_akivision.utils.purchase_order_payment_flow.frappe") as mock:
				mock.throw.side_effect = ValueError
				mock.db.get_value.side_effect = [
					frappe._dict(docstatus=1, company="C", supplier="S", currency="CNY", is_return=0),
					frappe._dict(parent="PR", item_code="ITEM", purchase_order="PO", purchase_order_item="POI")]
				mock.db.sql.return_value = confirmed
				if confirmed:
					validate_invoice_reconciliation(doc)
				else:
					with self.assertRaises(ValueError):
						validate_invoice_reconciliation(doc)

	def test_order_invoice_cannot_bypass_receipt(self):
		with patch("client_akivision.utils.purchase_order_payment_flow.frappe") as mock:
			mock.throw.side_effect = ValueError
			with self.assertRaises(ValueError):
				validate_invoice_reconciliation(frappe._dict(items=[frappe._dict(idx=1, purchase_order="PO")]))
