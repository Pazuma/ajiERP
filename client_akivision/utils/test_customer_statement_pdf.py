"""Regression checks for the concise customer statement presentation."""

import re
import unittest
from unittest.mock import patch

import frappe

from client_akivision.utils import customer_reconciliation_pdf as export


class TestCustomerStatementPDF(unittest.TestCase):

	def test_concise_statement_preserves_rows_and_balances(self):
		statement = frappe._dict(company="Test", party="Customer", currency="CNY", name="TEST",
			from_date="2026-08-01", to_date="2026-08-31", version=1, lines=[],
			order_billing_rows=[frappe._dict(order_date="2026-08-02", sales_order="SO-1",
				item_name="测试产品", ordered_qty=10, order_amount=100, billed_amount=40,
				paid_amount=20, outstanding_amount=20, uom="台", delivery_notes="DN-1")])
		with patch.object(export.frappe.db, "get_value", return_value="测试公司"), \
			patch.object(export, "nowdate", return_value="2026-08-31"), \
			patch.object(export, "_statement_bank_details", return_value={"bank_name": "测试银行", "bank_account_no": "1234"}), \
			patch.object(export, "render_pdf", return_value=b"pdf") as render, \
			patch("frappe.desk.utils.provide_binary_file"):
			export._download_saved_customer_account_statement(statement)
		data = render.call_args.args[1]
		self.assertEqual(data["order_rows"][0]["rate"], 10)
		self.assertEqual(data["outstanding_amount"], 80)
		self.assertEqual(data["order_amount"], data["paid_amount"] + data["outstanding_amount"])
		html = frappe.render_template(render.call_args.args[0], data)
		headers = re.findall(r"<th>(.*?)</th>", html)
		self.assertEqual(len(headers), 12)
		self.assertIn("送货单号", headers)
		self.assertIn("收款账户信息", html)
		self.assertIn("付款方确认", html)
		for removed in ("产品编码", "已开票量", "期初未结账单", "对账单编号", "导出日期"):
			self.assertNotIn(removed, html)

	def test_missing_bank_account_stays_blank(self):
		with patch.object(export.frappe, "get_list", return_value=[]):
			self.assertEqual(export._statement_bank_details("Test"), {"bank_name": "", "bank_account_no": ""})

	def test_bank_from_other_company_is_not_printed(self):
		with patch.object(export.frappe, "get_list", return_value=[frappe._dict(name="Bank")]), \
			patch.object(export, "read_doc", return_value=frappe._dict(is_company_account=1, company="Other")):
			self.assertEqual(export._statement_bank_details("Test")["bank_account_no"], "")

	def test_empty_orders_does_not_export_an_empty_zero_statement(self):
		with self.assertRaises(frappe.ValidationError):
			export._download_saved_customer_account_statement(frappe._dict(company="Test", lines=[], order_billing_rows=[]))
