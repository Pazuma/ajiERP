import unittest
from unittest.mock import patch

import frappe

from client_akivision.utils.inventory_impairment import assess_item, calculate_assessment


class TestInventoryImpairment(unittest.TestCase):
	def rule(self, **overrides):
		return dict(warehouse="Test Warehouse", start_date="2026-01-31", grace_months=3,
			period_months=1, period_ratio=5, max_ratio=50, basis_rate=100, **overrides)

	def test_full_months_grace_and_cap(self):
		rule = self.rule()
		for date, expected in [("2026-01-01", 0), ("2026-04-30", 0),
			("2026-05-30", 0), ("2026-05-31", 5), ("2026-06-30", 10), ("2028-01-31", 50)]:
			with self.subTest(date=date):
				result = calculate_assessment(rule, date, 10)
				self.assertEqual(result["impairment_ratio"], expected)
				self.assertEqual(result["reference_rate"], 100 - expected)
				self.assertEqual(result["impairment_amount"], expected * 10)

	def test_quarterly_and_nonpositive_stock(self):
		rule = self.rule()
		rule.update(grace_months=0, period_months=3)
		self.assertEqual(calculate_assessment(rule, "2026-04-29", 10)["impairment_ratio"], 0)
		self.assertEqual(calculate_assessment(rule, "2026-04-30", 10)["impairment_ratio"], 5)
		for qty in (0, -10):
			self.assertEqual(calculate_assessment(rule, "2026-05-31", qty)["impairment_amount"], 0)

	def test_year_day_and_legacy_month_boundaries(self):
		rule = self.rule()
		rule.update(grace_months=0, period_unit="年")
		self.assertEqual(calculate_assessment(rule, "2027-01-30", 1)["impairment_ratio"], 0)
		self.assertEqual(calculate_assessment(rule, "2027-01-31", 1)["impairment_ratio"], 5)
		rule.update(start_date="2024-02-29")
		self.assertEqual(calculate_assessment(rule, "2025-02-28", 1)["impairment_ratio"], 5)
		rule.update(start_date="2026-01-31", grace_months=1, period_unit="日", period_months=3)
		for date, expected in [("2026-02-27", 0), ("2026-03-02", 0), ("2026-03-03", 5), ("2026-03-06", 10)]:
			self.assertEqual(calculate_assessment(rule, date, 1)["impairment_ratio"], expected)
		rule = self.rule()
		legacy = calculate_assessment(rule, "2026-10-23", 10)
		rule["period_unit"] = "月"
		self.assertEqual(legacy, calculate_assessment(rule, "2026-10-23", 10))

	def test_invalid_rules(self):
		for field, value in [("warehouse", None), ("start_date", None), ("period_months", 0),
			("grace_months", -1), ("basis_rate", 0), ("period_ratio", 101), ("max_ratio", 0), ("period_unit", "周")]:
			rule = self.rule()
			rule[field] = value
			with self.subTest(field=field), patch.object(frappe, "throw", side_effect=ValueError):
				with self.assertRaises(ValueError):
					calculate_assessment(rule, "2026-10-20", 10)

	def test_legacy_rows_unchanged(self):
		row = frappe._dict(auto_assess=0, impairment_amount=123, status="已计提")
		doc = frappe._dict(custom_inventory_impairment_items=[row])
		assess_item(doc)
		self.assertEqual(row.impairment_amount, 123)
		self.assertEqual(row.status, "已计提")

	def test_save_calculates_and_rejects_duplicates(self):
		row = frappe._dict(self.rule())
		row.auto_assess = 1
		doc = frappe._dict(name="Test Item", custom_inventory_impairment_items=[row])
		with patch.object(frappe.db, "get_value", return_value=10), patch(
			"client_akivision.utils.inventory_impairment.today", return_value="2026-05-31"
		):
			assess_item(doc)
			self.assertEqual(row.impairment_amount, 50)
			self.assertEqual(row.status, "已评估（未计提）")
			doc.custom_inventory_impairment_items.append(frappe._dict(row))
			with patch.object(frappe, "throw", side_effect=ValueError), self.assertRaises(ValueError):
				assess_item(doc)
