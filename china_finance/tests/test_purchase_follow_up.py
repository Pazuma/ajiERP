import unittest
from unittest.mock import patch

import frappe

from china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up import (
	PurchaseFollowUp,
	validate_purchase_invoice_follow_up,
	validate_purchase_invoice_follow_up_amount,
)


class TestPurchaseFollowUp(unittest.TestCase):
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.get_doc")
	def test_invoice_company_and_supplier_must_match(self, get_doc):
		get_doc.return_value = frappe._dict(docstatus=1, company="A", supplier="S", currency="CNY")
		invoice = frappe._dict(custom_purchase_follow_up="PFU-1", company="B", supplier="S", currency="CNY", docstatus=0)
		with self.assertRaises(frappe.ValidationError):
			validate_purchase_invoice_follow_up(invoice)

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.get_doc")
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.has_permission", return_value=True)
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.get_value", return_value=100)
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.sql")
	def test_submitted_invoice_cannot_exceed_reconciled_amount(self, sql, get_value, has_permission, get_doc):
		get_doc.return_value = frappe._dict(docstatus=1, company="A", supplier="S", currency="CNY")
		sql.side_effect = [[frappe._dict(name="PFU-1")], [(60,)]]
		invoice = frappe._dict(custom_purchase_follow_up="PFU-1", name="PINV-2", company="A", supplier="S", currency="CNY", docstatus=0, grand_total=50, is_return=0)
		with self.assertRaises(frappe.ValidationError):
			validate_purchase_invoice_follow_up_amount(invoice)

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db")
	def test_unlinked_invoice_remains_on_standard_path(self, db):
		invoice = frappe._dict(custom_purchase_follow_up=None)
		validate_purchase_invoice_follow_up(invoice)
		validate_purchase_invoice_follow_up_amount(invoice)
		db.assert_not_called()

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.get_all")
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.exists", return_value=True)
	def test_payment_status_distinguishes_unpaid_and_partial(self, _exists, get_all):
		doc = PurchaseFollowUp.__new__(PurchaseFollowUp)
		doc.name = "PFU-1"
		get_all.return_value = [frappe._dict(name="PINV-1", docstatus=1, grand_total=100, outstanding_amount=100)]
		doc._refresh_invoice_status()
		self.assertEqual(doc.purchase_invoice_status, "待付款")
		get_all.return_value[0].outstanding_amount = 40
		doc._refresh_invoice_status()
		self.assertEqual(doc.purchase_invoice_status, "部分付款")
