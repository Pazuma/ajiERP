import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from china_finance.services.sales_settlement import ensure_initial_settlement_from_reconciliation
from china_finance.china_finance.services.customer_reconciliation_statement import get_customer_delivery_rows
from china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up import ensure_purchase_follow_up_from_statement
from china_finance.china_finance.doctype.china_reconciliation_statement.china_reconciliation_statement import ChinaReconciliationStatement


class TestAutoReconciliationDrafts(unittest.TestCase):
	@patch("china_finance.china_finance.services.customer_reconciliation_statement._validate_filters")
	@patch("china_finance.china_finance.services.customer_reconciliation_statement.frappe.get_all", return_value=[])
	def test_delivery_preview_only_loads_settlement_mode(self, get_all, validate_filters):
		get_customer_delivery_rows("A", "C", "2026-09-09", "2026-09-09")
		self.assertEqual(get_all.call_args.kwargs["filters"]["custom_china_settlement_mode"], "对账结算后确认应收")

	@patch("china_finance.china_finance.doctype.china_reconciliation_statement.china_reconciliation_statement.frappe.db.get_value")
	def test_delivery_statement_rejects_direct_mode(self, get_value):
		get_value.side_effect = [frappe._dict(docstatus=1), "直接确认应收"]
		statement = frappe._dict(statement_type="Customer", statement_basis="Delivery", party="C", company="A",
			from_date="2026-09-09", to_date="2026-09-09", lines=[frappe._dict(voucher_type="Delivery Note", voucher_no="DN-1", source_detail_name="ROW-1")])
		with self.assertRaises(frappe.ValidationError):
			ChinaReconciliationStatement.validate(statement)

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.ensure_purchase_follow_up_from_statement")
	def test_supplier_submission_creates_purchase_draft(self, ensure):
		statement = ChinaReconciliationStatement.__new__(ChinaReconciliationStatement)
		statement.name = "CNR-2"
		statement.statement_type = "Supplier"
		statement.confirmation_file = None
		statement.replaces = None
		ensure.return_value = {"name": "PFU-1"}
		statement.on_submit()
		ensure.assert_called_once_with(statement)

	def test_customer_ledger_does_not_create_draft(self):
		statement = ChinaReconciliationStatement.__new__(ChinaReconciliationStatement)
		statement.name = "CNR-3"
		statement.statement_type = "Customer"
		statement.statement_basis = "Ledger"
		statement.confirmation_file = None
		statement.replaces = None
		with patch("china_finance.services.sales_settlement.ensure_initial_settlement_from_reconciliation") as ensure:
			statement.on_submit()
			ensure.assert_not_called()

	@patch("china_finance.china_finance.doctype.china_reconciliation_statement.china_reconciliation_statement.create_archive_record")
	@patch("china_finance.services.sales_settlement.ensure_initial_settlement_from_reconciliation")
	def test_customer_delivery_submission_creates_initial_draft(self, ensure, archive):
		statement = ChinaReconciliationStatement.__new__(ChinaReconciliationStatement)
		statement.name = "CNR-1"
		statement.statement_type = "Customer"
		statement.statement_basis = "Delivery"
		statement.confirmation_file = None
		statement.replaces = None
		ensure.return_value = {"name": "CSTL-1"}
		statement.on_submit()
		ensure.assert_called_once_with("CNR-1")
		archive.assert_not_called()

	@patch("china_finance.services.sales_settlement.frappe.db.get_value", return_value="CSTL-1")
	@patch("china_finance.services.sales_settlement.frappe.db.sql")
	@patch("china_finance.services.sales_settlement.create_settlement_from_reconciliation")
	def test_existing_auto_draft_is_reused(self, create, sql, get_value):
		self.assertEqual(ensure_initial_settlement_from_reconciliation("CNR-1"), {"name": "CSTL-1"})
		create.assert_not_called()

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.get_value", return_value=None)
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.sql")
	def test_purchase_draft_has_no_source_without_invoice(self, sql, get_value):
		statement = frappe._dict(name="CNR-2", docstatus=1, status="Confirmed", statement_type="Supplier", lines=[])
		statement.check_permission = lambda permission: None
		result = ensure_purchase_follow_up_from_statement(statement)
		self.assertIsNone(result["name"])
		self.assertIn("reason", result)

	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.get_doc")
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.has_permission", return_value=True)
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.get_value")
	@patch("china_finance.china_finance.doctype.purchase_follow_up.purchase_follow_up.frappe.db.sql", return_value=[])
	def test_purchase_invoice_receipt_row_creates_draft(self, sql, get_value, has_permission, get_doc):
		statement = frappe._dict(name="CNR-4", docstatus=1, status="Confirmed", statement_type="Supplier",
			company="A", party="S", currency="CNY", from_date="2026-01-01", to_date="2026-01-31",
			lines=[frappe._dict(voucher_type="Purchase Invoice", voucher_no="PINV-1")])
		statement.check_permission = lambda permission: None
		invoice = SimpleNamespace(docstatus=1, company="A", supplier="S", currency="CNY", is_return=0,
			items=[frappe._dict(purchase_receipt="PREC-1", purchase_receipt_item="ROW-1", qty=3)])
		draft = frappe._dict(name="PFU-1")
		draft.insert = lambda: None
		get_doc.side_effect = [invoice, draft]
		get_value.side_effect = [None,
			frappe._dict(parent="PREC-1", purchase_order="PO-1", item_code="ITEM", item_name="Item", qty=3, rate=10, amount=30),
			frappe._dict(company="A", supplier="S", currency="CNY", posting_date="2026-01-10", docstatus=1, is_return=0)]
		self.assertEqual(ensure_purchase_follow_up_from_statement(statement), {"name": "PFU-1"})
		created = get_doc.call_args_list[-1].args[0]
		self.assertEqual(created["reconciliation_statement"], "CNR-4")
		self.assertEqual(created["sources"][0]["source_detail"], "ROW-1")
