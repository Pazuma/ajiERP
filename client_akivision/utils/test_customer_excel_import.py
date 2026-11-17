from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import frappe
from openpyxl import Workbook, load_workbook
from frappe.tests import IntegrationTestCase

from client_akivision.utils import customer_excel_import as customer_import
from client_akivision.client_akivision.api import data_import


class TestCustomerExcelImport(IntegrationTestCase):
	def setUp(self):
		self.code = "000-IMPORT-" + uuid4().hex[:10]
		self.person = frappe.get_doc({"doctype": "Sales Person", "sales_person_name": "测试业务" + uuid4().hex[:8],
			"enabled": 1, "is_group": 0}).insert()
		workbook = Workbook()
		workbook.active.append(list(customer_import.HEADERS))
		workbook.active.append([self.code, "客户导入测试", "张先生", "0013800000000", "测试账单地址", "测试收货地址", self.person.sales_person_name])
		output = BytesIO()
		workbook.save(output)
		self.file = frappe.get_doc({"doctype": "File", "file_name": "客户导入测试.xlsx",
			"is_private": 1, "content": output.getvalue()}).insert()

	def test_workbook_to_customer_and_related_documents(self):
		self.assertTrue(customer_import.matches(self.file.file_url))
		rows, warnings = customer_import.plan(self.file.file_url, "Insert New Records")
		self.assertEqual(warnings, [])
		name = customer_import.save_row(rows[0], "Insert New Records")
		self.assertEqual(name, self.code)
		customer = frappe.get_doc("Customer", name)
		self.assertEqual(customer.custom_responsible_sales_person, self.person.name)
		self.assertEqual(frappe.db.get_value("Contact", customer.customer_primary_contact, "mobile_no"), "0013800000000")
		self.assertEqual(frappe.db.get_value("Address", customer.customer_primary_address, "address_line1"), "测试账单地址")
		links = frappe.get_all("Dynamic Link", filters={"parenttype": "Address", "link_name": name}, pluck="parent")
		self.assertEqual(len(links), 2)
		self.assertTrue(customer_import.preview(self.file.file_url, "Insert New Records")["warnings"])
		rows, warnings = customer_import.plan(self.file.file_url, "Update Existing Records")
		self.assertEqual(warnings, [])
		customer_import.save_row(rows[0], "Update Existing Records")
		self.assertEqual(len(frappe.get_all("Dynamic Link", filters={"parenttype": "Address", "link_name": name})), 2)

	def test_unknown_sales_person_and_duplicate_codes_are_blocked(self):
		matrix = [list(customer_import.HEADERS), [self.code, "测试", "", "", "", "", "不存在的业务人员"],
			[self.code, "测试", "", "", "", "", ""]]
		with patch.object(data_import, "_raw_excel_matrix", return_value=matrix):
			rows, warnings = customer_import.plan(self.file.file_url, "Insert New Records")
		self.assertEqual(len(warnings), 2)
		self.assertFalse(frappe.db.exists("Customer", self.code))

	def test_download_template_has_exact_seven_headers(self):
		data_import.download_customer_import_template()
		workbook = load_workbook(BytesIO(frappe.response["filecontent"]))
		self.assertEqual(tuple(c.value for c in workbook.active[1]), customer_import.HEADERS)

	def test_inline_preview_routes_to_customer_branch(self):
		task = data_import.create_inline_import("Customer")
		preview = data_import.preview_inline_import(task["name"], self.file.file_url)
		self.assertEqual(preview["custom_mode"], "customer_seven_columns")
		self.assertEqual(preview["payload_count"], 1)
		self.assertEqual(preview["warnings"], [])
		self.assertFalse(frappe.db.exists("Customer", self.code))
		with patch.object(frappe.db, "commit"):
			result = data_import.run_inline_import(task["name"])
		self.assertEqual(result["status"], "Success")
		self.assertTrue(frappe.db.exists("Customer", self.code))
