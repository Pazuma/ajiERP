import frappe
from frappe.tests import IntegrationTestCase

from custom_filters.item_supplier_pricing import save_item_supplier_pricing_rule

from client_akivision.utils.purchase_comparison import (
	create_po_drafts,
	recalculate_comparison_row,
	run_comparison,
)


class TestPurchaseComparisonFormulaPricing(IntegrationTestCase):
	def setUp(self):
		suffix = frappe.generate_hash(length=8)
		self.company = frappe.db.get_value("Company", {}, "name")
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.uom = frappe.db.get_value("UOM", {}, "name")
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")

		self.supplier = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": f"_Test Comparison Supplier {suffix}",
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}).insert()
		self.item = frappe.get_doc({
			"doctype": "Item",
			"item_code": f"_TEST-COMPARISON-{suffix}",
			"item_name": f"Test Comparison Item {suffix}",
			"item_group": item_group,
			"stock_uom": self.uom,
			"is_stock_item": 0,
			"is_purchase_item": 1,
			"supplier_items": [{"supplier": self.supplier.name}],
		}).insert()
		self.supplier_row = self.item.supplier_items[0]

	def _save_rule(self, tiers, minimum_order_qty=0):
		return save_item_supplier_pricing_rule(
			self.item.name,
			self.supplier_row.name,
			self.supplier.name,
			{
				"rule_type": "Quantity Range",
				"uom": self.uom,
				"currency": self.currency,
				"company": self.company,
				"minimum_order_qty": minimum_order_qty,
				"tiers": tiers,
			},
		)

	def _make_comparison(self, qty):
		doc = frappe.get_doc({
			"doctype": "Purchase Comparison",
			"company": self.company,
			"status": "Draft",
			"items": [{
				"item_code": self.item.name,
				"item_name": self.item.item_name,
				"qty": qty,
				"uom": self.uom,
			}],
		})
		run_comparison(doc)
		doc.insert()
		return doc

	def test_formula_comparison_moq_recalculation_and_po_trace(self):
		rule = self._save_rule([
			{"min_qty": 1, "max_qty": 99, "rate": 10},
			{"min_qty": 100, "max_qty": 0, "rate": 8},
		], minimum_order_qty=20)
		comparison = self._make_comparison(5)

		self.assertEqual(len(comparison.rows), 1)
		row = comparison.rows[0]
		self.assertEqual(row.item_supplier_pricing_rule, rule["name"])
		self.assertEqual(row.calculation_qty, 20)
		self.assertEqual(row.recommended_rate, 10)
		self.assertEqual(row.source_currency, self.currency)

		result = recalculate_comparison_row(comparison.name, row.name, 100)
		self.assertEqual(result["order_qty"], 100)
		self.assertEqual(result["recommended_rate"], 8)
		self.assertEqual(result["order_total"], 800)

		purchase_orders = create_po_drafts(comparison.name)
		self.assertEqual(len(purchase_orders), 1)
		po = frappe.get_doc("Purchase Order", purchase_orders[0])
		self.assertEqual(po.custom_purchase_comparison, comparison.name)
		self.assertEqual(po.items[0].item_code, self.item.name)
		self.assertEqual(po.items[0].qty, 100)
		self.assertEqual(po.items[0].rate, 8)

	def test_new_rule_version_blocks_stale_comparison(self):
		old_rule = self._save_rule([{"min_qty": 1, "max_qty": 0, "rate": 10}])
		comparison = self._make_comparison(10)
		self.assertEqual(comparison.rows[0].item_supplier_pricing_rule, old_rule["name"])

		new_rule = self._save_rule([{"min_qty": 1, "max_qty": 0, "rate": 9}])
		self.assertNotEqual(new_rule["name"], old_rule["name"])
		with self.assertRaises(frappe.ValidationError):
			create_po_drafts(comparison.name)
