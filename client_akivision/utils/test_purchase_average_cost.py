import unittest
from types import SimpleNamespace
from unittest.mock import patch

from client_akivision.utils.purchase_average_cost import get_purchase_averages, weighted_average


class TestPurchaseAverageCost(unittest.TestCase):
	def test_quantity_weighted_not_simple_average(self):
		self.assertAlmostEqual(weighted_average(10 * 8 + 90 * 10, 100), 9.8)
		self.assertIsNone(weighted_average(100, 0))
		self.assertIsNone(weighted_average(-10, -1))

	@patch("client_akivision.utils.purchase_average_cost.frappe")
	def test_purchase_receipts_only_and_no_history(self, frappe):
		frappe.has_permission.return_value = True
		frappe.db.exists.return_value = True
		frappe.get_cached_value.return_value = "CNY"
		frappe.get_list.return_value = ["PR-1", "PR-2"]
		frappe.db.sql.return_value = [SimpleNamespace(item_code="RM", net_qty=100, net_amount=980, sample_count=2)]
		result = get_purchase_averages(["RM", "NEW"], "Test Company", "2026-01-01", "2026-12-31")
		self.assertEqual(result["RM"]["rate"], 9.8)
		self.assertIsNone(result["NEW"]["rate"])
		self.assertEqual(result["NEW"]["source"], "No Purchase History")
		query, params = frappe.db.sql.call_args.args
		self.assertIn("pr.docstatus = 1", query)
		self.assertIn("pr.is_return = 1", query)
		self.assertIn("Purchase Receipt Item", query)
		self.assertEqual(params["company"], "Test Company")
