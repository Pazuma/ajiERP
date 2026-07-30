from unittest.mock import patch

import frappe

from custom_filters.production_plan import get_items_for_material_requests


def test_production_plan_material_warehouses_are_applied_per_company():
	rows = [
		{"item_code": "ITEM-1", "warehouse": "Selected - C"},
		{"item_code": "ITEM-2", "warehouse": "Selected - C"},
		{"item_code": "ITEM-3", "warehouse": "Selected - C"},
	]

	with patch(
		"custom_filters.production_plan.erpnext_get_items_for_material_requests", return_value=rows
	), patch(
		"custom_filters.production_plan.frappe.get_all",
		side_effect=[
			[
				{"parent": "ITEM-1", "default_warehouse": "Item One - C"},
				{"parent": "ITEM-2", "default_warehouse": "Other Company - X"},
			],
			["Item One - C"],
		],
	):
		result = get_items_for_material_requests({"company": "Company C"})

	assert result[0]["warehouse"] == "Item One - C"
	assert result[1]["warehouse"] == "Selected - C"
	assert result[2]["warehouse"] == "Selected - C"


def test_production_plan_empty_result_is_unchanged():
	with patch(
		"custom_filters.production_plan.erpnext_get_items_for_material_requests", return_value=[]
	):
		assert get_items_for_material_requests({"company": "Company C"}) == []
