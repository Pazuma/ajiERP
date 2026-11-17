"""Transactional accounting and permission regression tests; no GL is generated."""

import unittest
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from china_finance.services.sales_order_finance_accounting import (
	DOCTYPE, accounting_key, calculate_totals, confirm_accounting, create_accounting_draft,
	create_revision, get_accounting_context, invalidate_invoice, source_context,
)
from china_finance.services.sales_order_finance_permissions import assert_finance_access


class TestFinanceAccountingCalculations(unittest.TestCase):
	def test_missing_and_explicit_zero_are_different(self):
		missing = calculate_totals([dict(net_amount=10000)], [])
		self.assertIsNone(missing["gross_profit"])
		zero = calculate_totals([dict(net_amount=10000, cost_complete=1, sales_cost=0)], [])
		self.assertEqual(zero["gross_profit"], 10000)

	def test_tax_and_expenses_do_not_change_gross_profit(self):
		values = calculate_totals([dict(net_amount=10000, cost_complete=1, sales_cost=6000, other_expenses=100)], [dict(amount=1300)], 2)
		self.assertEqual(values["gross_profit"], 4000)
		self.assertEqual(values["gross_margin"], 40)
		self.assertEqual(values["management_profit"], 3900)
		self.assertEqual(values["base_gross_profit"], 8000)

	def test_returns_reverse_profit_and_zero_revenue_has_no_margin(self):
		values = calculate_totals([dict(net_amount=-10000, cost_complete=1, sales_cost=-6000)], [])
		self.assertEqual(values["gross_profit"], -4000)
		self.assertIsNone(calculate_totals([dict(net_amount=0, cost_complete=1)], [])["gross_margin"])

	@patch("china_finance.services.sales_order_finance_permissions.frappe.get_roles", return_value=["Sales User", "Manufacturing Manager"])
	def test_sales_and_manufacturing_roles_do_not_grant_finance(self, _roles):
		with self.assertRaises(frappe.PermissionError):
			assert_finance_access(user="not-a-finance-user")


class TestSalesOrderFinanceAccounting(FrappeTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.company = frappe.db.get_value("Company", {}, "name")
		self.customer = frappe.db.get_value("Customer", {}, "name")
		self.item = frappe.db.get_value("Item", {}, "name")
		if not all((self.company, self.customer, self.item)):
			self.skipTest("A company, customer and item fixture are required")
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		# Minimal submitted source fixtures intentionally bypass accounting events:
		# tests exercise the new branch without creating real receivables or stock.
		self.order = self._source("Sales Order")
		self.order_item = self._row("Sales Order Item", self.order, qty=10, net_amount=10000, base_net_amount=10000)
		self.invoice = self._source("Sales Invoice")
		self.invoice_item = self._row("Sales Invoice Item", self.invoice, qty=10, net_amount=10000, base_net_amount=10000, sales_order=self.order.name, so_detail=self.order_item.name)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def _source(self, doctype, **values):
		doc = frappe.get_doc(dict(doctype=doctype, name="TEST-FIN-" + uuid4().hex[:16], company=self.company,
			customer=self.customer, currency=self.currency, conversion_rate=1, docstatus=1,
			posting_date=nowdate(), transaction_date=nowdate(), net_total=10000, grand_total=10000, **values))
		doc.db_insert()
		return doc

	def _row(self, doctype, parent, **values):
		row = frappe.get_doc(dict(doctype=doctype, name="TEST-FIN-ROW-" + uuid4().hex[:16], parent=parent.name,
			parenttype=parent.doctype, parentfield="items", idx=1, item_code=self.item, **values))
		row.db_insert()
		return row

	def _draft(self):
		return frappe.get_doc(DOCTYPE, create_accounting_draft(self.order.name, self.invoice.name))

	def _complete(self, doc):
		for row in doc.items:
			row.sales_cost = 6000
			row.cost_complete = 1
		doc.save()
		return doc

	def test_manual_confirm_revision_and_no_old_cost_overwrite(self):
		doc = self._complete(self._draft())
		self.assertEqual(doc.gross_profit, 4000)
		confirm_accounting(doc.name, str(doc.modified))
		doc.reload()
		self.assertEqual(doc.status, "已确认")
		self.assertEqual(doc.active_key, accounting_key(self.order.name, self.invoice.name))
		with self.assertRaises(frappe.ValidationError):
			doc.reason = "illegal direct edit"
			doc.save()
		revision = frappe.get_doc(DOCTYPE, create_revision(doc.name, "核对后调整成本"))
		revision.items[0].sales_cost = 6500
		revision.save()
		confirm_accounting(revision.name, str(revision.modified))
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "已替代")
		self.assertIsNone(frappe.db.get_value(DOCTYPE, doc.name, "active_key"))
		self.assertEqual(frappe.db.get_value(DOCTYPE, revision.name, "gross_profit"), 3500)
		if frappe.get_meta("Sales Order").has_field("custom_production_cost"):
			frappe.db.set_value("Sales Order", self.order.name, "custom_production_cost", 999)
			self.assertEqual(frappe.db.get_value(DOCTYPE, revision.name, "sales_cost"), 6500)

	def test_incomplete_confirmation_and_status_tampering_refused(self):
		doc = self._draft()
		with self.assertRaises(frappe.ValidationError):
			confirm_accounting(doc.name, str(doc.modified))
		doc.reload()
		doc.status = "已确认"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_duplicate_drafts_and_changed_invoice_snapshot(self):
		doc = self._complete(self._draft())
		self.assertEqual(create_accounting_draft(self.order.name, self.invoice.name), doc.name)
		frappe.db.set_value("Sales Invoice Item", self.invoice_item.name, "net_amount", 9000)
		with self.assertRaises(frappe.ValidationError):
			confirm_accounting(doc.name, str(doc.modified))

	def test_client_confirmation_flag_cannot_bypass_confirmation(self):
		doc = self._complete(self._draft())
		doc.flags.finance_confirm = True
		doc.status = "已确认"
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_source_cancel_invalidates_without_deleting_history(self):
		doc = self._complete(self._draft())
		confirm_accounting(doc.name, str(doc.modified))
		invalidate_invoice(self.invoice)
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "status"), "待复核")
		self.assertEqual(frappe.db.get_value(DOCTYPE, doc.name, "gross_profit"), 4000)
		self.assertIsNone(frappe.db.get_value(DOCTYPE, doc.name, "active_key"))

	def test_report_only_counts_effective_confirmations(self):
		from china_finance.china_finance.report.sales_order_finance_accounting_summary.sales_order_finance_accounting_summary import execute
		doc = self._complete(self._draft())
		filters = dict(company=self.company, sales_order=self.order.name)
		self.assertIsNone(execute(filters)[1][0].base_gross_profit)
		confirm_accounting(doc.name, str(doc.modified))
		self.assertEqual(execute(filters)[1][0].base_gross_profit, 4000)
		frappe.db.set_value("Sales Invoice Item", self.invoice_item.name, "net_amount", 9000)
		row = execute(filters)[1][0]
		self.assertEqual(row.status, "待复核")
		self.assertIsNone(row.base_gross_profit)

	def test_partial_and_multi_order_invoice_only_reads_matching_rows(self):
		second_order = self._source("Sales Order")
		second_row = self._row("Sales Order Item", second_order, qty=5, net_amount=5000)
		self._row("Sales Invoice Item", self.invoice, qty=5, net_amount=5000, sales_order=second_order.name, so_detail=second_row.name)
		frappe.db.set_value("Sales Invoice", self.invoice.name, "net_total", 15000)
		context = source_context(self.order.name, self.invoice.name)
		self.assertEqual(len(context["items"]), 1)
		self.assertEqual(context["items"][0]["net_amount"], 10000)
		second_invoice = self._source("Sales Invoice")
		self._row("Sales Invoice Item", second_invoice, qty=2, net_amount=2000, sales_order=self.order.name, so_detail=self.order_item.name)
		self.assertEqual(source_context(self.order.name, second_invoice.name)["items"][0]["net_amount"], 2000)

	def test_sales_user_cannot_call_or_read_records(self):
		doc = self._draft()
		user = frappe.get_doc(dict(doctype="User", email=f"finance-scope-{uuid4().hex[:10]}@example.test",
			first_name="Finance Scope", send_welcome_email=0, roles=[{"role": "Sales User"}])).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		with self.assertRaises(frappe.PermissionError):
			get_accounting_context(self.order.name)
		self.assertFalse(frappe.has_permission(DOCTYPE, "read", doc=doc))
		from frappe.model import get_permitted_fields
		self.assertNotIn("custom_production_cost", get_permitted_fields("Sales Order", user=user.name))
