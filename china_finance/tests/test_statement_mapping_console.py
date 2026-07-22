from types import SimpleNamespace

import frappe
from frappe.tests import UnitTestCase

from china_finance.services.statement_mapping_console import build_console_payload, update_template_formula


def _template(rows):
	return SimpleNamespace(
		name="企业会计准则|Balance Sheet|2.0",
		version="2.0",
		accounting_standard="企业会计准则",
		statement_type="Balance Sheet",
		rows=rows,
	)


def _row(row_code, row_type="Mapped Accounts", indent=0, **overrides):
	values = dict(
		row_code=row_code,
		label=row_code,
		row_type=row_type,
		indent=indent,
		bold=0,
		formula=None,
		balance_direction=None,
	)
	values.update(overrides)
	return SimpleNamespace(**values)


def _mapping(name, account, row_code, reviewed=1, sign_multiplier="1", **overrides):
	return SimpleNamespace(
		name=name,
		account=account,
		row_code=row_code,
		cash_inflow_row_code=None,
		cash_outflow_row_code=None,
		sign_multiplier=sign_multiplier,
		mapping_source="Automatic",
		reviewed=reviewed,
		effective_from=None,
		effective_to=None,
		**overrides,
	)


def _account(name, **overrides):
	return SimpleNamespace(
		name=name,
		account_name=name,
		account_number=None,
		root_type="Asset",
		account_type=None,
		**overrides,
	)


class TestStatementMappingConsolePayload(UnitTestCase):
	def test_mappings_grouped_by_row_and_summary_counts(self):
		template = _template(
			[
				_row("CURRENT_ASSETS", row_type="Heading"),
				_row("CASH", indent=1),
				_row("RECEIVABLES", indent=1),
			]
		)
		mappings = [
			_mapping("M1", "1001 - Cash", "CASH", reviewed=1),
			_mapping("M2", "1002 - Bank", "CASH", reviewed=0),
			_mapping("M3", "1122 - AR", "RECEIVABLES", reviewed=1),
		]
		accounts = [
			_account("1001 - Cash"),
			_account("1002 - Bank"),
			_account("1122 - AR"),
			_account("5001 - Cost"),
		]
		all_accounts = [
			SimpleNamespace(
				name="Assets", account_name="Assets", account_number=None,
				parent_account="", is_group=1, root_type="Asset",
			),
			SimpleNamespace(
				name="1001 - Cash", account_name="1001 - Cash", account_number="1001",
				parent_account="Assets", is_group=0, root_type="Asset",
			),
		]
		payload = build_console_payload(template, mappings, accounts, all_accounts)
		rows_by_code = {row["row_code"]: row for row in payload["rows"]}
		self.assertEqual(len(rows_by_code["CASH"]["mappings"]), 2)
		self.assertEqual(len(rows_by_code["RECEIVABLES"]["mappings"]), 1)
		self.assertEqual(rows_by_code["CURRENT_ASSETS"]["mappings"], [])
		self.assertEqual(
			payload["summary"],
			{
				"total_leaf_accounts": 4,
				"mapped_accounts": 3,
				"unmapped_accounts": 1,
				"total_mappings": 3,
				"pending_review": 1,
			},
		)
		self.assertEqual([a.name for a in payload["unmapped_accounts"]], ["5001 - Cost"])
		self.assertEqual(payload["template"]["statement_type"], "Balance Sheet")
		self.assertEqual(len(payload["accounts"]), 2)
		self.assertEqual(payload["accounts"][0]["is_group"], 1)
		self.assertEqual(payload["accounts"][1]["parent_account"], "Assets")

	def test_sign_multiplier_is_normalized(self):
		template = _template([_row("CASH")])
		mappings = [
			_mapping("M1", "A1", "CASH", sign_multiplier="-1"),
			_mapping("M2", "A2", "CASH", sign_multiplier="1"),
			_mapping("M3", "A3", "CASH", sign_multiplier="something-else"),
		]
		payload = build_console_payload(template, mappings, [_account("A1"), _account("A2"), _account("A3")])
		signs = [item["sign_multiplier"] for item in payload["rows"][0]["mappings"]]
		self.assertEqual(signs, [-1, 1, 1])

	def test_mapping_without_leaf_account_still_renders(self):
		template = _template([_row("CASH")])
		mappings = [_mapping("M1", "9999 - Disabled", "CASH")]
		payload = build_console_payload(template, mappings, [])
		item = payload["rows"][0]["mappings"][0]
		self.assertEqual(item["account_name"], "9999 - Disabled")
		self.assertIsNone(item["account_number"])
		self.assertEqual(payload["summary"]["mapped_accounts"], 1)
		self.assertEqual(payload["summary"]["unmapped_accounts"], 0)

	def test_reviewed_flag_and_pending_count(self):
		template = _template([_row("CASH")])
		mappings = [
			_mapping("M1", "A1", "CASH", reviewed=1),
			_mapping("M2", "A2", "CASH", reviewed=0),
			_mapping("M3", "A3", "CASH", reviewed=0),
		]
		payload = build_console_payload(template, mappings, [_account("A1"), _account("A2"), _account("A3")])
		self.assertEqual(payload["summary"]["pending_review"], 2)
		self.assertTrue(payload["rows"][0]["mappings"][0]["reviewed"])
		self.assertFalse(payload["rows"][0]["mappings"][1]["reviewed"])


class _FakeTemplateDoc:
	def __init__(self, rows):
		self.name = "企业会计准则|Balance Sheet|2.0"
		self.rows = rows
		self.saved = False

	def save(self):
		self.saved = True


class TestUpdateTemplateFormula(UnitTestCase):
	def test_updates_formula_and_saves(self):
		doc = _FakeTemplateDoc([_row("TOTAL", row_type="Formula", formula="A + B")])
		result = update_template_formula(doc, "TOTAL", "  A + B + C  ")
		self.assertTrue(doc.saved)
		self.assertEqual(doc.rows[0].formula, "A + B + C")
		self.assertEqual(result, {"template": doc.name, "row_code": "TOTAL", "formula": "A + B + C"})

	def test_missing_row_code_throws(self):
		doc = _FakeTemplateDoc([_row("TOTAL", row_type="Formula")])
		with self.assertRaises(frappe.ValidationError):
			update_template_formula(doc, "MISSING", "A + B")

	def test_non_formula_row_throws(self):
		doc = _FakeTemplateDoc([_row("CASH", row_type="Mapped Accounts")])
		with self.assertRaises(frappe.ValidationError):
			update_template_formula(doc, "CASH", "A + B")
