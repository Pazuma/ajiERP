import unittest

from custom_filters.pricing_formula import evaluate_rule, normalize_rule


class TestPricingFormula(unittest.TestCase):
	def test_fixed_rate(self):
		result = evaluate_rule({"rule_type": "Fixed Rate", "parameters": {"rate": 10}}, 25)
		self.assertEqual(result["rate"], 10)
		self.assertEqual(result["total"], 250)

	def test_quantity_range_boundary(self):
		rule = {
			"rule_type": "Quantity Range",
			"parameters": {
				"tiers": [
					{"min_qty": 1, "max_qty": 99, "rate": 10},
					{"min_qty": 100, "max_qty": 499, "rate": 9},
					{"min_qty": 500, "max_qty": 0, "rate": 8},
				]
			},
		}
		self.assertEqual(evaluate_rule(rule, 99)["rate"], 10)
		self.assertEqual(evaluate_rule(rule, 100)["rate"], 9)
		self.assertEqual(evaluate_rule(rule, 500)["rate"], 8)
		finite_rule = {
			"rule_type": "Quantity Range",
			"parameters": {"tiers": [
				{"min_qty": 1, "max_qty": 10, "rate": 20},
				{"min_qty": 11, "max_qty": 40, "rate": 5},
			]},
		}
		self.assertEqual(evaluate_rule(finite_rule, 41)["rate"], 5)
		self.assertIn("按最后一档", evaluate_rule(finite_rule, 41)["matched_tier"])

	def test_step_discount_stops_at_minimum(self):
		rule = {
			"rule_type": "Step Discount",
			"parameters": {
				"base_rate": 10,
				"start_qty": 100,
				"step_qty": 100,
				"discount_percent": 5,
				"minimum_rate": 7,
			},
		}
		self.assertEqual(evaluate_rule(rule, 99)["rate"], 10)
		self.assertEqual(evaluate_rule(rule, 100)["rate"], 9.5)
		self.assertEqual(evaluate_rule(rule, 1000)["rate"], 7)

	def test_progressive_discount(self):
		rule = {
			"rule_type": "Progressive Discount",
			"parameters": {
				"base_rate": 10,
				"start_qty": 100,
				"step_qty": 100,
				"discount_percent": 10,
				"minimum_rate": 0,
			},
		}
		self.assertEqual(evaluate_rule(rule, 200)["rate"], 8.1)

	def test_overlapping_tiers_rejected(self):
		with self.assertRaises(ValueError):
			normalize_rule({
				"rule_type": "Tier Table",
				"parameters": {"tiers": [
					{"min_qty": 1, "max_qty": 100, "rate": 10},
					{"min_qty": 100, "max_qty": 200, "rate": 9},
				]},
			})

	def test_invalid_discount_rejected(self):
		with self.assertRaises(ValueError):
			normalize_rule({
				"rule_type": "Step Discount",
				"parameters": {"base_rate": 10, "start_qty": 100, "step_qty": 10, "discount_percent": 101, "minimum_rate": 1},
			})
