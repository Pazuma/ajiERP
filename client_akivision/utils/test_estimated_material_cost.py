import unittest
from types import SimpleNamespace
from unittest.mock import patch

from client_akivision.utils import estimated_material_cost as service


class TestEstimatedMaterialCost(unittest.TestCase):
	@patch.object(service.frappe, "get_roles", return_value=["Manufacturing User"])
	@patch.object(service.frappe, "throw", side_effect=PermissionError)
	def test_production_cannot_preview_cost(self, _throw, _roles):
		with self.assertRaises(PermissionError):
			service.preview_estimated_material_cost("BOM", "BOM-1")

	@patch.object(service.frappe, "get_doc")
	def test_nested_bom_uses_stock_quantity_once(self, get_doc):
		parent = SimpleNamespace(
			quantity=2, items=[SimpleNamespace(item_code="SUB", stock_qty=4, bom_no="BOM-SUB")],
			check_permission=lambda *_: None,
		)
		child = SimpleNamespace(
			quantity=2, items=[SimpleNamespace(item_code="RAW", stock_qty=6, bom_no=None)],
			check_permission=lambda *_: None,
		)
		get_doc.side_effect = lambda _, name: {"BOM-PARENT": parent, "BOM-SUB": child}[name]
		self.assertEqual(service._bom_requirements("BOM-PARENT", 2), {"RAW": 12})

	@patch.object(service, "get_purchase_averages")
	@patch.object(service.frappe, "get_roles", return_value=["Accounts User"])
	@patch.object(service.frappe, "get_cached_value", return_value="CNY")
	@patch.object(service.frappe, "get_doc")
	def test_missing_history_never_creates_total(self, get_doc, _currency, _roles, averages):
		get_doc.return_value = SimpleNamespace(
			company="Test Company", required_items=[SimpleNamespace(item_code="RAW", required_qty=3)],
			check_permission=lambda *_: None,
		)
		averages.return_value = {"RAW": {"rate": None, "source": "No Purchase History", "sample_count": 0, "from_date": "2026-01-01", "to_date": "2026-12-31"}}
		result = service.preview_estimated_material_cost("Work Order", "WO-1")
		self.assertIsNone(result["estimated_material_amount"])
		self.assertEqual(result["missing_items"], ["RAW"])
