import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from client_akivision.client_akivision.api.operations_kpi import (
	get_drilldown_permissions,
	get_monthly_collection_completion,
	get_purchase_order_delay_status,
	metric,
	percent,
	resolve_aging_rule,
)


class TestOperationsKPIHelpers(unittest.TestCase):
	def test_percent_handles_zero_denominator(self):
		self.assertEqual(percent(100, 0), 0)
		self.assertEqual(percent(25, 100), 0.25)

	def test_aging_rule_uses_configured_bounds(self):
		rules = [
			frappe._dict(label="正常", from_days=0, to_days=30, risk_level="低风险"),
			frappe._dict(label="超期", from_days=31, to_days=None, risk_level="高风险"),
		]
		self.assertEqual(resolve_aging_rule(30, rules), ("正常", "低风险"))
		self.assertEqual(resolve_aging_rule(31, rules), ("超期", "高风险"))

	def test_purchase_order_not_due_is_pending_not_delayed(self):
		rows = [
			frappe._dict(
				purchase_order="PO-001",
				supplier="SUP-001",
				supplier_name="Supplier",
				qty=10,
				received_qty=0,
				expected_date="2026-07-20",
				receipt_date=None,
			)
		]
		result = get_purchase_order_delay_status(rows, "2026-07-14")
		self.assertEqual(result[0].status, "pending")
		self.assertEqual(result[0].delay_days, 0)

	def test_purchase_order_uses_latest_item_delay(self):
		rows = [
			frappe._dict(
				purchase_order="PO-002",
				supplier="SUP-001",
				supplier_name="Supplier",
				qty=10,
				received_qty=10,
				expected_date="2026-07-10",
				receipt_date="2026-07-11",
			),
			frappe._dict(
				purchase_order="PO-002",
				supplier="SUP-001",
				supplier_name="Supplier",
				qty=5,
				received_qty=0,
				expected_date="2026-07-08",
				receipt_date=None,
			),
		]
		result = get_purchase_order_delay_status(rows, "2026-07-14")
		self.assertEqual(result[0].status, "delayed")
		self.assertEqual(result[0].delay_days, 6)

	def test_metric_without_target_has_no_target_progress(self):
		result = metric(20, "Currency")
		self.assertIsNone(result["target_direction"])
		self.assertIsNone(result["target_progress"])
		self.assertEqual(result["status"], "未设置")

	def test_metric_target_progress_for_higher_is_better(self):
		target = frappe._dict(target_value=100, evaluation_direction="Higher Is Better")
		result = metric(25, "Currency", target)
		self.assertEqual(result["target_progress"], 25)
		self.assertEqual(result["achievement"], 0.25)
		self.assertEqual(result["status"], "正常")

	def test_metric_target_progress_for_lower_is_better(self):
		target = frappe._dict(target_value=100, evaluation_direction="Lower Is Better")
		below_target = metric(50, "Currency", target)
		over_target = metric(200, "Currency", target)
		self.assertEqual(below_target["achievement"], 1)
		self.assertEqual(below_target["target_progress"], 100)
		self.assertEqual(over_target["achievement"], 0.5)
		self.assertEqual(over_target["target_progress"], 50)

	def test_metric_target_progress_handles_zero_target(self):
		target = frappe._dict(target_value=0, evaluation_direction="Lower Is Better")
		self.assertEqual(metric(0, "Int", target)["target_progress"], 100)
		self.assertEqual(metric(1, "Int", target)["target_progress"], 0)

	def test_metric_target_progress_handles_empty_value(self):
		target = frappe._dict(target_value=100, evaluation_direction="Higher Is Better")
		result = metric(None, "Currency", target)
		self.assertIsNone(result["target_progress"])
		self.assertEqual(result["status"], "未设置")

	def test_monthly_collection_completion_uses_target_value(self):
		target = frappe._dict(target_value=200, evaluation_direction="Higher Is Better")
		result = get_monthly_collection_completion(50, target)
		self.assertEqual(result["value"], 0.25)

	@patch("client_akivision.client_akivision.api.operations_kpi.frappe")
	def test_drilldown_permissions_follow_report_permissions(self, mock_frappe):
		def get_report(_doctype, report_name):
			return SimpleNamespace(is_permitted=lambda: report_name != "Receivable Aging Analysis")

		mock_frappe.db.exists.return_value = True
		mock_frappe.get_cached_doc.side_effect = get_report
		self.assertEqual(
			get_drilldown_permissions(),
			{
				"sales_order_list": True,
				"receivable_aging_analysis": False,
				"purchase_delay_analysis": True,
			},
		)
