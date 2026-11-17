from copy import deepcopy
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from china_finance.services.tax_calculation import _vat_calculation, _validate_request
from china_finance.services.tax_worksheet import _merge, save_worksheet, apply_worksheet


class TestTaxWorksheet(FrappeTestCase):
	def setUp(self):
		self.company = frappe.db.get_value("Company", {}, "name")
		self.period = "2098-02"
		self.result = _vat_calculation(self.company, self.period, "2098-02-01", "2098-02-28")
		self.values = dict(OUTPUT_VAT=10000, DEDUCTIBLE_INPUT_VAT=6000, INPUT_VAT_TRANSFER=500,
			OPENING_VAT_CREDIT=1000, VAT_EXEMPT=0, VAT_PREPAID=0)

	def test_missing_is_not_verified_zero_and_drilldown(self):
		self.assertEqual(self.result["rows"][0]["source_count"], 0)
		self.assertEqual(self.result["rows"][0]["source_state"], "missing")
		self.assertEqual(self.result["rows"][0]["source_filters"]["direction"], "销项")
		self.assertEqual(self.result["rows"][1]["source_filters"]["deduction_period"],
			["between", ["2098-02-01", "2098-02-28"]])

	def test_vat_calculation_and_unsupported_branch(self):
		result = _merge(deepcopy(self.result), self.values, True)
		self.assertEqual(result["status"], "Calculated")
		self.assertEqual(result["rows"][6]["amount"], 3500)
		self.assertEqual(result["rows"][7]["amount"], 0)
		self.assertEqual(_merge(deepcopy(self.result), self.values | {"VAT_PREPAID": 1}, True)["status"], "Incomplete")
		self.assertEqual(_merge(deepcopy(self.result), {}, True)["status"], "Incomplete")
		credit = _merge(deepcopy(self.result), self.values | {"OUTPUT_VAT": 0}, True)
		self.assertEqual(credit["rows"][7]["amount"], 6500)

	def test_version_confirmation_and_source_change(self):
		args = dict(company=self.company, period=self.period, tax_type="VAT", values=self.values,
			basis="测试凭据及常规政策", ordinary_vat=1)
		first = save_worksheet(**args)
		with self.assertRaises(frappe.TimestampMismatchError):
			save_worksheet(**args)
		second = save_worksheet(**args, previous_version=first["name"], confirm=1)
		data = apply_worksheet(self.company, self.period, "VAT", deepcopy(self.result))
		self.assertEqual(data["status"], "Confirmed")
		self.assertEqual(data["worksheet"]["name"], second["name"])
		changed = deepcopy(self.result)
		changed["rows"][0]["amount"] = 1
		self.assertEqual(apply_worksheet(self.company, self.period, "VAT", changed)["status"], "Incomplete")
		self.assertEqual(frappe.get_doc("China Tax Worksheet Snapshot", first["name"]).status, "Draft")

	def test_rejects_invalid_values_incomplete_and_permissions(self):
		args = dict(company=self.company, period=self.period, tax_type="VAT", basis="依据")
		for values in ({"unexpected": 1}, {"OUTPUT_VAT": "NaN"}, {"OUTPUT_VAT": "abc"}):
			with self.assertRaises(frappe.ValidationError):
				save_worksheet(**args, values=values)
		with self.assertRaises(frappe.ValidationError):
			save_worksheet(**args, values={}, confirm=1)
		with patch("frappe.only_for", side_effect=frappe.PermissionError):
			with self.assertRaises(frappe.PermissionError):
				save_worksheet(**args, values={})
		with patch("frappe.has_permission", return_value=False):
			with self.assertRaises(frappe.PermissionError):
				_validate_request(self.company, self.period, "VAT")
