from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from openpyxl import Workbook, load_workbook

from client_akivision.utils import item_excel_import as item_import
from client_akivision.client_akivision.api import data_import


class TestItemExcelImport(IntegrationTestCase):
	def setUp(self):
		self.code = "000-ITEM-" + uuid4().hex[:10]
		self.group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		workbook = Workbook()
		workbook.active.append(list(item_import.HEADERS))
		workbook.active.append([self.group, self.code, "三列物料测试"])
		output = BytesIO()
		workbook.save(output)
		self.file = frappe.get_doc({"doctype": "File", "file_name": "物料三列测试.xlsx",
			"is_private": 1, "content": output.getvalue()}).insert()

	def test_preview_runner_and_defaults(self):
		task = data_import.create_inline_import("Item")
		preview = data_import.preview_inline_import(task["name"], self.file.file_url)
		self.assertEqual(preview["custom_mode"], "item_three_columns")
		self.assertEqual(preview["warnings"], [])
		self.assertFalse(frappe.db.exists("Item", self.code))
		with patch.object(frappe.db, "commit"):
			result = data_import.run_inline_import(task["name"])
		self.assertEqual(result["status"], "Success")
		item = frappe.get_doc("Item", self.code)
		self.assertEqual(item.item_group, self.group)
		self.assertEqual(item.item_name, "三列物料测试")
		for field, default in item_import.DEFAULTS.items():
			self.assertEqual(str(item.get(field)) if field == "end_of_life" else item.get(field), default, field)
		self.assertEqual(item.stock_uom, item_import.stock_uom())
		self.assertEqual(item.uoms[0].conversion_factor, 1)
		self.assertEqual(item.description, item.item_name)
		self.assertTrue(item_import.preview(self.file.file_url, "Insert New Records")["warnings"])

	def test_update_preserves_business_settings(self):
		rows, warnings = item_import.plan(self.file.file_url, "Insert New Records")
		self.assertEqual(warnings, [])
		item_import.save_row(rows[0], "Insert New Records")
		frappe.db.set_value("Item", self.code, {"is_sales_item": 1, "is_purchase_item": 0})
		rows[0]["物料名称"] = "更新名称"
		item_import.save_row(rows[0], "Update Existing Records")
		item = frappe.get_doc("Item", self.code)
		self.assertEqual(item.item_name, "更新名称")
		self.assertEqual(item.is_sales_item, 1)
		self.assertEqual(item.is_purchase_item, 0)

	def test_invalid_group_duplicate_missing_and_extra_fields(self):
		matrix = [list(item_import.HEADERS), ["不存在的分类", self.code, "测试"],
			[self.group, self.code, "测试"], [self.group, "", "测试"]]
		with patch.object(data_import, "_raw_excel_matrix", return_value=matrix):
			_, warnings = item_import.plan(self.file.file_url, "Insert New Records")
		self.assertEqual(len(warnings), 3)
		matrix = [list(item_import.HEADERS) + ["额外字段"], [self.group, self.code, "测试", 1]]
		with patch.object(data_import, "_raw_excel_matrix", return_value=matrix):
			self.assertTrue(item_import.plan(self.file.file_url, "Insert New Records")[1])
		self.assertFalse(frappe.db.exists("Item", self.code))

	def test_template(self):
		data_import.download_item_import_template()
		workbook = load_workbook(BytesIO(frappe.response["filecontent"]))
		self.assertEqual(tuple(c.value for c in workbook.active[1]), item_import.HEADERS)
