from unittest import TestCase
from unittest.mock import patch

import frappe

from mes_integration.mes_integration.purchase_order import (
	_group_rows,
	_rate_from_rule,
	_summarize_arrivals,
	build_aggregate_pricing_result,
)


class TestPurchaseOrderPricing(TestCase):
	def test_same_item_different_warehouses_are_grouped(self):
		rows = [
			frappe._dict(item_code="SCREW", stock_uom="Nos", stock_qty=100, warehouse="A"),
			frappe._dict(item_code="SCREW", stock_uom="Nos", stock_qty=200, warehouse="B"),
		]
		groups = _group_rows(rows)
		self.assertEqual(len(groups), 1)
		self.assertEqual(sum(row.stock_qty for row in groups[("SCREW", "Nos")]), 300)

	def test_rule_rate_is_applied_to_each_row(self):
		row = frappe._dict(price_list_rate=0.1, rate=0.1, precision=lambda field: 6)
		self.assertEqual(_rate_from_rule(row, frappe._dict(price_list_rate=0.08)), (0.08, 0.0, 0.0, 0.08))

	def test_rule_rate_is_converted_back_to_purchase_uom(self):
		row = frappe._dict(price_list_rate=1, rate=1, conversion_factor=10, precision=lambda field: 6)
		self.assertEqual(_rate_from_rule(row, frappe._dict(price_list_rate=0.08)), (0.8, 0.0, 0.0, 0.8))

	@patch("erpnext.accounts.doctype.pricing_rule.pricing_rule.get_pricing_rule_for_item")
	def test_aggregate_pricing_uses_buying_transaction_type(self, get_pricing_rule):
		get_pricing_rule.return_value = frappe._dict()
		doc = frappe._dict(
			doctype="Purchase Order",
			name="new-purchase-order",
			supplier="Supplier",
			currency="CNY",
			buying_price_list="Standard Buying",
			items=[
				frappe._dict(
					name="POI-1", item_code="SCREW", stock_uom="Nos", stock_qty=100,
					price_list_rate=1, rate=1, conversion_factor=1,
				),
				frappe._dict(
					name="POI-2", item_code="SCREW", stock_uom="Nos", stock_qty=200,
					price_list_rate=1, rate=1, conversion_factor=1,
				),
			],
		)

		build_aggregate_pricing_result(doc)

		self.assertEqual(get_pricing_rule.call_args.args[0].transaction_type, "buying")

	def test_actual_arrival_summary_excludes_unrelated_rows(self):
		order_items = [frappe._dict(name="POI-1", item_code="SCREW", item_name="Screw", qty=10, uom="Nos", rate=0.08)]
		arrivals = [frappe._dict(purchase_order_item="POI-1", qty=4), frappe._dict(purchase_order_item="OTHER", qty=9)]
		summary = _summarize_arrivals(order_items, arrivals)
		self.assertEqual(summary[0]["received_qty"], 4)
		self.assertEqual(summary[0]["remaining_qty"], 6)
