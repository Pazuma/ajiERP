from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from openpyxl import Workbook, load_workbook

from client_akivision.client_akivision.api import data_import
from client_akivision.utils import supplier_excel_import as supplier_import


class TestSupplierExcelImport(IntegrationTestCase):
	def setUp(self):
		self.code = "000-SUP-" + uuid4().hex[:10]
		self.bank = "测试开户银行" + uuid4().hex[:8]
		self.values = [self.code, "测试供应商", "王先生", "0013800000000", "测试供应商地址",
			"合作中", "A级", 30, "导入测试备注", "供方简称", "测试账户户名", "0001234567890123456789", self.bank]
		workbook = Workbook()
		workbook.active.append(list(supplier_import.HEADERS))
		workbook.active.append(self.values)
		output = BytesIO()
		workbook.save(output)
		self.file = frappe.get_doc({"doctype": "File", "file_name": "供应商测试.xlsx", "is_private": 1,
			"content": output.getvalue()}).insert()

	def test_download_template(self):
		data_import.download_supplier_import_template()
		workbook = load_workbook(BytesIO(frappe.response["filecontent"]))
		self.assertEqual(tuple(cell.value for cell in workbook.active[1]), supplier_import.HEADERS)

	def test_inline_preview_and_full_import(self):
		task = data_import.create_inline_import("Supplier")
		preview = data_import.preview_inline_import(task["name"], self.file.file_url)
		self.assertEqual(preview["custom_mode"], "supplier_flat_columns")
		self.assertEqual(preview["warnings"], [])
		self.assertFalse(frappe.db.exists("Supplier", self.code))
		with patch.object(frappe.db, "commit"):
			result = data_import.run_inline_import(task["name"])
		self.assertEqual(result["status"], "Success")
		supplier = frappe.get_doc("Supplier", self.code)
		self.assertEqual(supplier.custom_supplier_code, self.code)
		self.assertEqual(supplier.custom_supplier_short_name, "供方简称")
		self.assertEqual(supplier.custom_credit_days, 30)
		self.assertEqual(supplier.custom_supplier_rating, "A级")
		self.assertEqual(frappe.db.get_value("Contact", supplier.supplier_primary_contact, "mobile_no"), "0013800000000")
		self.assertEqual(frappe.db.get_value("Address", supplier.supplier_primary_address, "address_line1"), "测试供应商地址")
		account = frappe.get_doc("Bank Account", supplier.default_bank_account)
		self.assertEqual(account.bank_account_no, self.values[-2])
		self.assertEqual(account.account_name, self.values[-3])
		self.assertEqual(account.bank, self.bank)
		self.assertEqual(account.party, self.code)
		self.assertTrue(supplier_import.preview(self.file.file_url, "Insert New Records")["warnings"])
		rows, warnings = supplier_import.plan(self.file.file_url, "Update Existing Records")
		self.assertEqual(warnings, [])
		supplier_import.save_row(rows[0], "Update Existing Records")
		self.assertEqual(frappe.db.count("Bank Account", {"party_type": "Supplier", "party": self.code}), 1)
		self.assertEqual(frappe.db.count("Dynamic Link", {"parenttype": "Contact", "link_doctype": "Supplier", "link_name": self.code}), 1)
		self.assertEqual(frappe.db.count("Dynamic Link", {"parenttype": "Address", "link_doctype": "Supplier", "link_name": self.code}), 1)

	def test_invalid_days_status_bank_and_duplicates(self):
		for column, value in (("账期天数", "-1"), ("账期天数", "1.5"), ("合作状态", "未知状态"), ("开户行名称", "")):
			values = list(self.values)
			values[supplier_import.HEADERS.index(column)] = value
			with patch.object(data_import, "_raw_excel_matrix", return_value=[list(supplier_import.HEADERS), values]):
				self.assertTrue(supplier_import.preview(self.file.file_url, "Insert New Records")["warnings"])
		with patch.object(data_import, "_raw_excel_matrix", return_value=[list(supplier_import.HEADERS), self.values, self.values]):
			self.assertTrue(supplier_import.preview(self.file.file_url, "Insert New Records")["warnings"])

	def test_empty_optional_cells_preserve_values(self):
		rows, warnings = supplier_import.plan(self.file.file_url, "Insert New Records")
		supplier_import.save_row(rows[0], "Insert New Records")
		minimal = {"供应商编号": self.code, "供应商名称": "更新供应商名称", "excel_row": 2}
		supplier_import.save_row(minimal, "Update Existing Records")
		supplier = frappe.get_doc("Supplier", self.code)
		self.assertEqual(supplier.supplier_name, "更新供应商名称")
		self.assertEqual(supplier.custom_credit_days, 30)
		self.assertTrue(supplier.default_bank_account)

	def test_manual_supplier_code_renames_record_and_links(self):
		rows, warnings = supplier_import.plan(self.file.file_url, "Insert New Records")
		self.assertEqual(warnings, [])
		supplier_import.save_row(rows[0], "Insert New Records")
		new_code = self.code + "-EDITED"
		supplier = frappe.get_doc("Supplier", self.code)
		supplier.custom_supplier_code = new_code
		supplier.save()
		self.assertFalse(frappe.db.exists("Supplier", self.code))
		self.assertTrue(frappe.db.exists("Supplier", new_code))
		self.assertEqual(frappe.db.get_value("Supplier", new_code, "custom_supplier_code"), new_code)
		self.assertEqual(frappe.db.get_value("Bank Account", supplier.default_bank_account, "party"), new_code)
		self.assertTrue(frappe.db.exists("Dynamic Link", {
			"parenttype": "Contact", "link_doctype": "Supplier", "link_name": new_code
		}))
		self.assertTrue(frappe.db.exists("Dynamic Link", {
			"parenttype": "Address", "link_doctype": "Supplier", "link_name": new_code
		}))
