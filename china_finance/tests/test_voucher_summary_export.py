import csv
import io
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from china_finance.services.voucher_summary import _csv_value, export_selected_vouchers


class TestSelectedVoucherExport(FrappeTestCase):
	def test_csv_formula_is_escaped(self):
		self.assertEqual(_csv_value("=1+1"), "'=1+1")
		self.assertEqual(_csv_value("  @cmd"), "'  @cmd")
		self.assertEqual(_csv_value("普通摘要"), "普通摘要")

	@patch("china_finance.services.voucher_summary.frappe.only_for")
	def test_empty_and_duplicate_selection_rejected(self, _only_for):
		with self.assertRaises(frappe.ValidationError):
			export_selected_vouchers([], {"company": "Test"})
		with self.assertRaises(frappe.ValidationError):
			export_selected_vouchers(["A", "A"], {"company": "Test"})

	@patch("china_finance.services.voucher_summary._query")
	@patch("china_finance.services.voucher_summary.frappe.has_permission")
	@patch("china_finance.services.voucher_summary.frappe.only_for")
	def test_only_selected_rows_are_exported(self, _only_for, permission, query):
		query.return_value = ([], [
			frappe._dict(name="A", statutory_number="记1", source_name="JE-1", posting_date="2026-09-01", remarks="=formula", debit=10, credit=10),
			frappe._dict(name="B", statutory_number="记2", source_name="JE-2", posting_date="2026-09-02", remarks="note", debit=20, credit=20),
		], {}, "2026-09-01", "2026-09-30")
		try:
			export_selected_vouchers(["B"], {"company": "Test"})
			rows = list(csv.reader(io.StringIO(frappe.response["filecontent"].lstrip("\ufeff"))))
			self.assertEqual(len(rows), 2)
			self.assertEqual(rows[1][:2], ["记2", "JE-2"])
			permission.assert_any_call("China Accounting Voucher", "read", "B", throw=True)
			with self.assertRaises(frappe.ValidationError):
				export_selected_vouchers(["C"], {"company": "Test"})
		finally:
			for key in ("filename", "filecontent", "type"):
				frappe.response.pop(key, None)
