import json
import unittest
from unittest.mock import patch

import frappe

from client_akivision.api.product_cost_quotation import get_sales_order_quote_options
from client_akivision.utils.sales_order_product_cost import (
	get_order_quote_snapshots,
	save_quote_snapshots,
	validate_quote_snapshots,
)


def _scenario():
	return frappe._dict(
		quantity=100,
		show_in_customer_quote=1,
		full_unit_cost=12.5,
		material_unit_cost=7,
		manufacturing_unit_cost=3,
		investment_unit_cost=2.5,
		suggested_price_with_rd=20,
		suggested_price_without_rd=18,
		final_tax_inclusive_price=22.6,
		gross_margin=44.7,
		batch_gross_profit=1010,
	)


def _quote(scenarios=None):
	return frappe._dict(
		name="PCQ-1", modified="2026-10-22 10:00:00", docstatus=1, item_code="FG-1",
		project="PROJ-1", company="Example Co", currency="CNY", exchange_rate=1,
		scenarios=scenarios or [_scenario()],
	)


class TestSalesOrderProductCost(unittest.TestCase):
	def _order(self, row, name=None):
		return frappe._dict(
			doctype="Sales Order", name=name, company="Example Co", currency="CNY",
			items=[row], flags=frappe._dict(),
		)

	def _row(self, name=None):
		return frappe._dict(
			name=name, idx=1, item_code="FG-1", rate=22.6,
			custom_cost_quotation="PCQ-1", custom_cost_quotation_batch=100,
			custom_cost_quotation_price_used=1,
		)

	def test_validates_and_prepares_private_snapshot(self):
		row = self._row()
		item = frappe._dict(custom_default_cost_quotation="PCQ-1", custom_development_project="PROJ-1")
		with patch.object(frappe, "get_doc", side_effect=[item, _quote()]), \
			patch.object(frappe.db, "exists", return_value=None):
			order = self._order(row)
			validate_quote_snapshots(order)
		snapshot = order.flags.sales_order_cost_quote_snapshots[0]
		payload = json.loads(snapshot["snapshot_json"])
		self.assertEqual(payload["full_unit_cost"], 12.5)
		self.assertTrue(payload["price_applied"])
		self.assertEqual(snapshot["idx"], 1)

	def test_saves_snapshot_using_persisted_child_name(self):
		row = self._row(name="SO-ITEM-0001")
		order = self._order(row, name="SO-1")
		order.flags.sales_order_cost_quote_snapshots = [{
			"idx": 1, "item_code": "FG-1", "quotation": "PCQ-1", "batch": 100,
			"price_applied": True, "company": "Example Co", "currency": "CNY",
			"project": "PROJ-1", "snapshot_json": '{"gross_margin":44.7}',
		}]
		with patch.object(frappe.db, "exists", return_value=None), \
			patch.object(frappe, "get_doc") as get_doc:
			save_quote_snapshots(order)
			get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)
			data = get_doc.call_args.args[0]
		self.assertEqual(data["sales_order_item_key"], "SO-ITEM-0001")
		self.assertEqual(data["item_code"], "FG-1")
		self.assertTrue(data["price_applied"])

	def test_save_is_idempotent(self):
		row = self._row(name="SO-ITEM-0001")
		order = self._order(row, name="SO-1")
		order.flags.sales_order_cost_quote_snapshots = [{
			"idx": 1, "item_code": "FG-1", "quotation": "PCQ-1", "batch": 100,
			"price_applied": True, "company": "Example Co", "currency": "CNY",
			"project": "PROJ-1", "snapshot_json": "{}",
		}]
		with patch.object(frappe.db, "exists", return_value="SNAP-1"), \
			patch.object(frappe, "get_doc") as get_doc:
			save_quote_snapshots(order)
		get_doc.assert_not_called()

	def test_public_options_exclude_internal_tiers(self):
		private = _scenario()
		private.quantity = 500
		private.show_in_customer_quote = 0
		with patch.object(frappe, "has_permission"), \
			patch.object(frappe.db, "get_value", side_effect=["PCQ-1", "PROJ-1"]), \
			patch.object(frappe, "get_doc", return_value=_quote([_scenario(), private])):
			result = get_sales_order_quote_options("FG-1", "Example Co", "CNY")
		self.assertEqual(result["scenarios"], [{"quantity": 100, "price": 22.6}])
		self.assertNotIn("full_unit_cost", result["scenarios"][0])

	def test_non_finance_user_cannot_read_snapshots(self):
		with patch.object(frappe, "get_roles", return_value=["Sales User"]), \
			patch.object(frappe, "throw", side_effect=ValueError("denied")), \
			self.assertRaises(ValueError):
			get_order_quote_snapshots("SO-1")

	def test_rejects_non_customer_quote_tier(self):
		row = self._row()
		scenario = _scenario()
		scenario.show_in_customer_quote = 0
		item = frappe._dict(custom_default_cost_quotation="PCQ-1", custom_development_project=None)
		with patch.object(frappe, "get_doc", side_effect=[item, _quote([scenario])]), \
			patch.object(frappe.db, "exists", return_value=None), \
			patch.object(frappe, "throw", side_effect=ValueError("private tier")), \
			self.assertRaises(ValueError):
			validate_quote_snapshots(self._order(row))


if __name__ == "__main__":
	unittest.main()
