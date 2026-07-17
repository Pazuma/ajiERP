from frappe.tests import IntegrationTestCase

from client_akivision.client_akivision.report.purchase_recommendation.purchase_recommendation import (
	_best_purchase,
	_hit_tier,
	_normalize_tiers,
	_quotation_tiers,
)


class TestPurchaseRecommendation(IntegrationTestCase):
	def test_direct_hit_within_tier(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 99, "rate": 10},
				{"min_qty": 100, "max_qty": 499, "rate": 8},
			]
		)
		result = _best_purchase(tiers, 50)
		self.assertEqual(result["direct_rate"], 10)
		self.assertEqual(result["direct_total"], 500)
		self.assertEqual(result["recommended_qty"], 50)
		self.assertEqual(result["recommended_total"], 500)
		self.assertEqual(result["savings"], 0)

	def test_round_up_to_next_tier_saves_money(self):
		# Spec example: demand 95, tier 1-99 @ 10 (total 950), tier 100-499 @ 8
		# (buy 100 -> total 800). Buying 5 more saves 150, recommend 100.
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 99, "rate": 10},
				{"min_qty": 100, "max_qty": 499, "rate": 8},
			]
		)
		result = _best_purchase(tiers, 95)
		self.assertEqual(result["direct_total"], 950)
		self.assertEqual(result["recommended_qty"], 100)
		self.assertEqual(result["recommended_rate"], 8)
		self.assertEqual(result["recommended_total"], 800)
		self.assertEqual(result["savings"], 150)

	def test_round_up_not_recommended_when_total_is_higher(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 99, "rate": 10},
				{"min_qty": 100, "max_qty": 499, "rate": 9.9},
			]
		)
		result = _best_purchase(tiers, 95)
		self.assertEqual(result["recommended_qty"], 95)
		self.assertEqual(result["savings"], 0)

	def test_demand_below_lowest_tier_recommends_cheapest_tier_start(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 100, "max_qty": 499, "rate": 8},
				{"min_qty": 500, "max_qty": 0, "rate": 7},
			]
		)
		result = _best_purchase(tiers, 50)
		self.assertIsNone(result["direct_total"])
		self.assertEqual(result["recommended_qty"], 100)
		self.assertEqual(result["recommended_total"], 800)
		self.assertIsNone(result["savings"])

	def test_unlimited_max_qty_tier(self):
		tiers = _normalize_tiers([{"min_qty": 1, "max_qty": 0, "rate": 10}])
		result = _best_purchase(tiers, 95)
		self.assertEqual(result["recommended_qty"], 95)
		self.assertEqual(result["recommended_total"], 950)

	def test_equal_total_keeps_smaller_qty(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 99, "rate": 10},
				{"min_qty": 100, "max_qty": 0, "rate": 9.5},
			]
		)
		result = _best_purchase(tiers, 95)
		self.assertEqual(result["recommended_qty"], 95)
		self.assertEqual(result["savings"], 0)

	def test_gap_between_tiers_hits_no_direct_tier(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 50, "rate": 10},
				{"min_qty": 100, "max_qty": 0, "rate": 8},
			]
		)
		result = _best_purchase(tiers, 75)
		self.assertIsNone(result["direct_total"])
		self.assertEqual(result["recommended_qty"], 100)
		self.assertEqual(result["recommended_total"], 800)
		self.assertIsNone(result["savings"])

	def test_higher_priority_wins_on_same_min_qty(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 10, "max_qty": 99, "rate": 10, "priority": 1},
				{"min_qty": 10, "max_qty": 99, "rate": 9, "priority": 5},
			]
		)
		self.assertEqual(_hit_tier(tiers, 50)["rate"], 9)

	def test_deepest_matching_tier_wins(self):
		tiers = _normalize_tiers(
			[
				{"min_qty": 1, "max_qty": 0, "rate": 10},
				{"min_qty": 100, "max_qty": 0, "rate": 8},
			]
		)
		self.assertEqual(_hit_tier(tiers, 150)["rate"], 8)
		self.assertEqual(_hit_tier(tiers, 99)["rate"], 10)

	def test_quotation_multiple_qty_rows_become_tiers(self):
		quote = {
			"rows": [
				{"idx": 1, "qty": 500, "rate": 50},
				{"idx": 2, "qty": 200, "rate": 150},
			]
		}
		tiers = _quotation_tiers(quote)
		self.assertEqual([tier["min_qty"] for tier in tiers], [200, 500])
		# Demand 499 hits the 200-tier @150; rounding up to 500 @50 saves money.
		result = _best_purchase(tiers, 499)
		self.assertEqual(result["direct_rate"], 150)
		self.assertEqual(result["direct_total"], 74850)
		self.assertEqual(result["recommended_qty"], 500)
		self.assertEqual(result["recommended_total"], 25000)
		self.assertEqual(result["savings"], 49850)

	def test_quotation_single_row_is_flat_price(self):
		self.assertIsNone(_quotation_tiers({"rows": [{"idx": 1, "qty": 700, "rate": 50}]}))
		self.assertIsNone(_quotation_tiers({"rows": []}))

	def test_quotation_same_qty_later_row_wins(self):
		quote = {
			"rows": [
				{"idx": 1, "qty": 100, "rate": 80},
				{"idx": 2, "qty": 100, "rate": 75},
			]
		}
		self.assertIsNone(_quotation_tiers(quote))
		quote["rows"].append({"idx": 3, "qty": 500, "rate": 50})
		tiers = _quotation_tiers(quote)
		self.assertEqual(_hit_tier(tiers, 100)["rate"], 75)
