import copy
import json
import unittest

from client_akivision.utils.product_cost_calculation import calculate


def example():
    return {"tax_rate": 13, "target_margin": 40, "cost_ratio": 40, "pricing_method": "Target Margin",
            "minimum_sales_qty": 200,
            "materials": [{"name": "part", "item_code": "PART", "qty_per_unit": 3, "conversion_factor": 1,
                           "pack_multiple": 1, "price_exchange_rate": 1, "tax_basis": "Exclusive",
                           "price_basis": "Supplier Rule", "surplus_policy": "Reusable"}],
            "operations": [{"operation": "组装", "charging_basis": "Per Unit", "standard_hours": 1,
                            "hourly_rate": 80, "included_cost_scope": "人工"}],
            "investments": [], "scenarios": [{"quantity": q} for q in (50, 100, 200, 500)]}


class TestProductCostCalculation(unittest.TestCase):
    def test_purchase_tier_uses_component_quantity(self):
        quantities = []
        def price(row, qty):
            quantities.append(float(qty))
            return {"rate": 10 if qty < 600 else 8}
        result = calculate(example(), price)
        self.assertEqual(quantities, [150, 300, 600, 1500])
        self.assertEqual(result[0]["material_unit_cost"], 30)
        self.assertEqual(result[2]["material_unit_cost"], 24)
        self.assertAlmostEqual(result[2]["gross_margin"], 40, places=5)

    def test_tax_extraction_and_moq_surplus(self):
        doc = example()
        row = doc["materials"][0]
        row.update(minimum_order_qty=1000, pack_multiple=100, tax_basis="Inclusive", purchase_tax_rate=13)
        result = calculate(doc, lambda row, qty: {"rate": 11.3})[0]
        self.assertEqual(result["material_unit_cost"], 30)
        self.assertEqual(result["procurement_total"], 10000)
        self.assertEqual(result["surplus_total"], 8500)
        row["surplus_policy"] = "Charge Batch"
        self.assertEqual(calculate(doc, lambda row, qty: {"rate": 11.3})[0]["material_unit_cost"], 200)

    def test_missing_price_is_incomplete(self):
        def missing(row, qty):
            raise ValueError("未维护阶梯价格")
        row = calculate(example(), missing)[0]
        self.assertEqual(row["completeness"], "Incomplete")
        self.assertIn("未维护阶梯价格", row["warnings"])

    def test_missing_tax_basis_blocks_confirmation(self):
        doc = example()
        doc["materials"][0]["tax_basis"] = ""
        self.assertTrue(calculate(doc, lambda r, q: {"rate": 10})[0]["missing"])

    def test_inclusive_tax_requires_rate(self):
        doc = example()
        doc["materials"][0].update(tax_basis="Inclusive", purchase_tax_rate="")
        self.assertIn("必须填写采购税率", calculate(doc, lambda r, q: {"rate": 10})[0]["warnings"])

    def test_batch_hours_and_override(self):
        doc = example()
        doc["operations"][0].update(charging_basis="Per Batch", tier_overrides_json='{"50": 2}')
        rows = calculate(doc, lambda r, q: {"rate": 10})
        self.assertEqual(rows[0]["manufacturing_unit_cost"], 3.2)
        self.assertEqual(rows[1]["manufacturing_unit_cost"], 0.8)

    def test_project_budget_not_added_and_recovery_not_double_counted(self):
        doc = example()
        doc["investments"] = [{"expense_type": "研发", "actual_amount": 10000, "budget_reference": 90000,
                               "remaining_estimate": 2000, "allocation_percent": 50, "recovered_amount": 1000,
                               "separate_charge": 1000, "recovery_method": "Mixed", "amortization_qty": 200}]
        row = calculate(doc, lambda r, q: {"rate": 10})[2]
        self.assertEqual(row["investment_unit_cost"], 20)  # (12000*50%-1000-1000)/200
        self.assertEqual(row["full_unit_cost"], 130)
        self.assertEqual(row["payback_qty"], 38)  # ceil(4000 / (130/.6 - 110))

    def test_separate_charge_must_cover_remaining(self):
        doc = example()
        doc["investments"] = [{"actual_amount": 1000, "allocation_percent": 100, "recovery_method": "Separate", "separate_charge": 500}]
        self.assertIn("单独收费未覆盖", calculate(doc, lambda r, q: {"rate": 10})[0]["warnings"])

    def test_investment_requires_explicit_recovery_quantity(self):
        doc = example()
        doc["investments"] = [{"expense_type": "研发", "actual_amount": 10000, "allocation_percent": 100,
                               "recovery_method": "Amortize"}]
        self.assertIn("请填写研发回收数量", calculate(doc, lambda r, q: {"rate": 10})[0]["warnings"])

    def test_cost_ratio_is_not_margin(self):
        doc = example()
        doc["pricing_method"] = "Cost Ratio"
        result = calculate(doc, lambda r, q: {"rate": 10})[0]
        self.assertAlmostEqual(result["gross_margin"], 60, places=5)

    def test_invalid_numbers_and_quantities(self):
        for field, value in (("target_margin", 100), ("cost_ratio", 0), ("tax_rate", "NaN"), ("tax_rate", -1)):
            doc = example()
            doc[field] = value
            with self.assertRaises(ValueError):
                calculate(doc, lambda r, q: {"rate": 10})
        doc = example()
        doc["scenarios"][0]["quantity"] = 100
        with self.assertRaises(ValueError):
            calculate(doc, lambda r, q: {"rate": 10})

    def test_loss_applied_once(self):
        doc = example()
        doc["materials"][0].update(loss_method="Quantity", loss_rate=10)
        result = calculate(doc, lambda r, q: {"rate": 10})[0]
        self.assertAlmostEqual(result["material_unit_cost"], 30 / .9, places=5)
        doc["materials"][0]["loss_method"] = "Cost"
        self.assertEqual(calculate(doc, lambda r, q: {"rate": 10})[0]["material_unit_cost"], 33)

    def test_automatic_price_follows_cost_but_manual_override_is_retained(self):
        doc = example()
        first = calculate(doc, lambda r, q: {"rate": 10})
        doc["scenarios"] = [copy.deepcopy(r) for r in first]
        second = calculate(doc, lambda r, q: {"rate": 20})
        self.assertGreater(second[0]["final_tax_inclusive_price"], first[0]["final_tax_inclusive_price"])
        doc["scenarios"][0].update(final_tax_inclusive_price=1, price_override_reason="测试负贡献")
        row = calculate(doc, lambda r, q: {"rate": 20})[0]
        self.assertEqual(row["payback_qty"], 0)
        self.assertIn("无法回本", row["warnings"])

    def test_input_not_mutated(self):
        doc = example()
        before = json.dumps(doc, sort_keys=True)
        calculate(doc, lambda r, q: {"rate": 10})
        self.assertEqual(before, json.dumps(doc, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
