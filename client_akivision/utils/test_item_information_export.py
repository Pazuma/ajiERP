from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from openpyxl import load_workbook

from client_akivision.utils import item_information_export as export


class TestItemInformationExport(FrappeTestCase):
	def test_selected_items_balances_and_reorder_only_warehouse(self):
		item = frappe._dict(name="MAT-1", item_name="螺丝", item_group="五金", disabled=0, stock_uom="个", safety_stock=15)
		context = {"items": {"MAT-1": {"warehouses": [
			{"warehouse": "原料仓", "actual_qty": 10}, {"warehouse": "生产仓", "actual_qty": -2}],
			"reorder_levels": [{"warehouse": "空仓", "warehouse_reorder_level": 12}]}}}
		with patch.object(export.frappe, "has_permission"), patch.object(export.frappe, "get_meta") as meta, patch.object(export.frappe, "get_list", return_value=[item]), patch.object(export, "get_item_list_stock_context", return_value=context):
			meta.return_value.get_permitted_fieldnames.return_value = list(item.keys())
			summary, details = export.build_item_information_rows(["MAT-1", "MAT-1"])
			self.assertEqual(summary, [["MAT-1", "螺丝", "五金", "启用", "个", 15, 8]])
			self.assertIn(["MAT-1", "螺丝", "空仓", "个", 0, 12], details)
			self.assertIn(["MAT-1", "螺丝", "生产仓", "个", -2, None], details)

	def test_inaccessible_selection_is_rejected(self):
		with patch.object(export.frappe, "has_permission"), patch.object(export.frappe, "get_meta") as meta, patch.object(export.frappe, "get_list", return_value=[]):
			meta.return_value.get_permitted_fieldnames.return_value = ["item_name", "item_group", "disabled", "stock_uom", "safety_stock"]
			with self.assertRaises(frappe.PermissionError):
				export.build_item_information_rows(["FORBIDDEN"])

	def test_workbook_has_two_sheets_and_literal_item_text(self):
		with patch.object(export, "build_item_information_rows", return_value=([["=1+1", "螺丝", "五金", "启用", "个", 15, 0]], [])), patch.object(export, "provide_binary_file") as download:
			export.download_item_information(["=1+1"])
			workbook = load_workbook(BytesIO(download.call_args.args[2]))
			self.assertEqual(workbook.sheetnames, ["物料汇总", "仓库库存明细"])
			self.assertEqual(workbook["物料汇总"]["A5"].value, "=1+1")
			self.assertEqual(workbook["物料汇总"]["A5"].data_type, "s")
