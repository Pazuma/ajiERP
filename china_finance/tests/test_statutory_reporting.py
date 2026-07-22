import io
import json
import zipfile
from types import SimpleNamespace

import frappe
from frappe.tests import UnitTestCase

from china_finance.services.financial_statement import (
	apply_temporary_inventory_accrual_presentation,
	apply_vat_net_presentation,
	get_mapping_for_date,
	render_rows,
	validate_formula_graph,
)
from china_finance.services.statutory_reporting import _build_excel
from china_finance.setup.templates import ENTERPRISE_ROWS, build_seed_rows


def row(code, row_type="Mapped Accounts", formula=None, direction="Debit Positive"):
	return SimpleNamespace(
		row_code=code, statutory_line_number=None, label=code, row_type=row_type,
		formula=formula, balance_direction=direction, indent=0, bold=0, show_zero=1,
	)


class TestStatutoryFormulaEngine(UnitTestCase):
	def test_formula_dependency_order_is_independent_of_row_order(self):
		template = SimpleNamespace(rows=[
			row("TOTAL", "Formula", "SUBTOTAL + C"),
			row("A"), row("SUBTOTAL", "Formula", "A + B"), row("B"), row("C"),
		])
		result = {item["row_code"]: item["amount"] for item in render_rows(template, {"A": 1, "B": 2, "C": 3})}
		self.assertEqual(result["SUBTOTAL"], 3)
		self.assertEqual(result["TOTAL"], 6)

	def test_formula_cycle_is_rejected(self):
		rows = [row("A", "Formula", "B + 1"), row("B", "Formula", "A + 1")]
		with self.assertRaises(frappe.ValidationError):
			validate_formula_graph(rows)

	def test_statutory_line_numbers_are_separate_and_contiguous(self):
		seed_rows = build_seed_rows(ENTERPRISE_ROWS["Profit and Loss"])
		line_numbers = [int(item["statutory_line_number"]) for item in seed_rows if item["row_type"] != "Heading"]
		self.assertEqual(line_numbers, list(range(1, len(line_numbers) + 1)))
		self.assertTrue(all(item["statutory_line_number"] is None for item in seed_rows if item["row_type"] == "Heading"))

	def test_mapping_revision_is_selected_by_posting_date(self):
		revisions = {
			"1002 - TEST": [
				SimpleNamespace(effective_from="2026-01-01", effective_to="2026-06-30", row_code="A"),
				SimpleNamespace(effective_from="2026-07-01", effective_to=None, row_code="B"),
			]
		}
		self.assertEqual(get_mapping_for_date(revisions, "1002 - TEST", "2026-03-01").row_code, "A")
		self.assertEqual(get_mapping_for_date(revisions, "1002 - TEST", "2026-08-01").row_code, "B")

	def test_deductible_vat_is_presented_as_other_current_asset(self):
		values = {"OTHER_CURRENT_ASSETS": 0, "TAXES_PAYABLE": 0}
		apply_vat_net_presentation(values, 69.03)
		self.assertEqual(values["OTHER_CURRENT_ASSETS"], 69.03)
		self.assertEqual(values["TAXES_PAYABLE"], 0)

	def test_net_output_vat_is_presented_as_tax_payable(self):
		values = {"OTHER_CURRENT_ASSETS": 0, "TAXES_PAYABLE": 0}
		apply_vat_net_presentation(values, -8.97)
		self.assertEqual(values["OTHER_CURRENT_ASSETS"], 0)
		self.assertEqual(values["TAXES_PAYABLE"], 8.97)

	def test_debit_temporary_inventory_accrual_is_presented_as_current_asset(self):
		values = {"OTHER_CURRENT_ASSETS": 0, "ACCOUNTS_PAYABLE": 0}
		apply_temporary_inventory_accrual_presentation(values, 90)
		self.assertEqual(values["OTHER_CURRENT_ASSETS"], 90)
		self.assertEqual(values["ACCOUNTS_PAYABLE"], 0)

	def test_formal_excel_contains_four_table_metadata_and_notes(self):
		payload = {
			"rows": [{"statutory_line_number": "1", "label": "货币资金", "amount": 1, "comparison_amount": 0}],
			"financial_statement_notes": {
				"from_date": "2026-01-01", "to_date": "2026-12-31", "version": 1,
				"disclosures": {"basis_of_preparation": "按企业会计准则编制"},
				"policies": [], "statement_data": {},
			},
		}
		snapshot = SimpleNamespace(
			statement_type="Balance Sheet", from_date="2026-01-01", to_date="2026-12-31",
			template_version="3.0", approved_by="Administrator", approved_on="2026-12-31 12:00:00",
			data_json=json.dumps(payload, ensure_ascii=False),
		)
		content = _build_excel([snapshot], "测试公司")
		self.assertTrue(content.startswith(b"PK"))
		with zipfile.ZipFile(io.BytesIO(content)) as workbook:
			workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
			self.assertIn("资产负债表", workbook_xml)
			self.assertIn("财务报表附注", workbook_xml)
