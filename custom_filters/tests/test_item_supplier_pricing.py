import frappe
from frappe.tests import IntegrationTestCase

from custom_filters.item_supplier_pricing import get_item_supplier_pricing_overview, save_item_supplier_pricing_rule
from custom_filters.pricing_formula import evaluate_supplier_rule, get_active_rule


class TestItemSupplierPricing(IntegrationTestCase):
	def test_save_fixed_rule_and_link_item_supplier(self):
		suffix = frappe.generate_hash(length=8)
		uom = frappe.db.get_value("UOM", {}, "name")
		item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		currency = frappe.db.get_single_value("Global Defaults", "default_currency") or "CNY"

		supplier = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": f"_Test Formula Supplier {suffix}",
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}).insert()
		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": f"_TEST-FORMULA-{suffix}",
			"item_name": f"Test Formula Item {suffix}",
			"item_group": item_group,
			"stock_uom": uom,
			"is_stock_item": 0,
			"supplier_items": [{"supplier": supplier.name, "supplier_part_no": "PART-001"}],
		}).insert()
		row = item.supplier_items[0]

		result = save_item_supplier_pricing_rule(
			item.name,
			row.name,
			supplier.name,
			{
				"rule_type": "Fixed Rate",
				"uom": uom,
				"currency": currency,
				"minimum_order_qty": 10,
				"parameters": {"rate": 12.5},
			},
		)

		linked = frappe.db.get_value(
			"Item Supplier", row.name, ["custom_active_pricing_rule", "custom_pricing_rule_summary"], as_dict=True
		)
		self.assertEqual(linked.custom_active_pricing_rule, result["name"])
		self.assertIn("12.5", linked.custom_pricing_rule_summary)
		overview = get_item_supplier_pricing_overview(item.name)
		self.assertFalse(overview["no_permission"])
		self.assertEqual(float(overview["rules"][result["name"]]["parameters"]["rate"]), 12.5)
		self.assertEqual(overview["rules"][result["name"]]["supplier"], supplier.name)
		active = get_active_rule(item.name, supplier.name)
		self.assertEqual(active.name, result["name"])
		calculated = evaluate_supplier_rule(active, 5)
		self.assertEqual(calculated["calculation_qty"], 10)
		self.assertEqual(calculated["rate"], 12.5)
		self.assertTrue(frappe.db.exists("Item Price", {"item_code": item.name, "supplier": supplier.name, "custom_item_supplier_pricing_rule": active.name}))
