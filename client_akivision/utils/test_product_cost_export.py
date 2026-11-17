from io import BytesIO
import unittest
from zipfile import ZipFile

import frappe
from openpyxl import load_workbook

from client_akivision.utils.product_cost_export import export_workbook
from client_akivision.utils.test_product_cost_sources import draft


class TestProductCostExport(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.savepoint("pcq_export")

    def tearDown(self):
        frappe.db.rollback(save_point="pcq_export")

    def test_internal_and_customer_files(self):
        doc = draft().insert()
        internal = load_workbook(BytesIO(export_workbook(doc, "internal")))
        self.assertIn("物料阶梯明细", internal.sheetnames)
        self.assertEqual(internal.worksheets[0]["N22"].value, 110)
        self.assertIn("草稿", internal.worksheets[0]["A7"].value)
        data = export_workbook(doc, "customer")
        customer = load_workbook(BytesIO(data))
        self.assertEqual(len(customer.worksheets), 1)
        self.assertLessEqual(customer.active.max_column, 11)
        self.assertEqual(customer.active["G11"].value, 50)
        self.assertEqual(customer.active["J11"].value, 500)
        with ZipFile(BytesIO(data)) as archive:
            self.assertFalse(any("externalLink" in name for name in archive.namelist()))
        for sheet in customer:
            self.assertFalse(sheet.sheet_state == "hidden")
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type, "f")
                    self.assertNotIn("陆小龙", str(cell.value))
                    self.assertNotIn("18029324088", str(cell.value))

    def test_overflow_quantities_paginated_and_formula_strings_safe(self):
        doc = draft()
        doc.product_name = "=HYPERLINK(\"http://example.invalid\")"
        for q in (1000, 2000, 3000, 5000, 6000, 7000, 8000, 9000):
            doc.append("scenarios", {"quantity": q})
        doc.insert()
        customer = load_workbook(BytesIO(export_workbook(doc, "customer")))
        self.assertEqual(len(customer.worksheets), 3)
        self.assertEqual(customer.worksheets[-1]["J11"].value, 9000)
        self.assertEqual(customer.active["C12"].data_type, "s")
        internal = load_workbook(BytesIO(export_workbook(doc, "internal")))
        self.assertEqual(internal.active["Y4"].value, 9000)

    def test_package_template_has_no_external_links_or_sample_data(self):
        path = frappe.get_app_path("client_akivision", "templates", "xlsx", "product_cost_quotation.xlsx")
        with ZipFile(path) as archive:
            self.assertFalse(any("externalLink" in name for name in archive.namelist()))
        book = load_workbook(path, keep_links=False)
        for sheet in book:
            for row in sheet:
                for cell in row:
                    self.assertNotEqual(cell.data_type, "f")
                    self.assertNotIn("陆小龙", str(cell.value))
                    self.assertNotIn("18029324088", str(cell.value))

    def test_customer_selection_does_not_remove_internal_scenarios(self):
        doc = draft().insert()
        doc.scenarios[0].show_in_customer_quote = 0
        customer = load_workbook(BytesIO(export_workbook(doc, "customer")))
        self.assertEqual(customer.active["G11"].value, 100)
        internal = load_workbook(BytesIO(export_workbook(doc, "internal")))
        self.assertEqual(internal.active["N4"].value, 50)
        for row in doc.scenarios:
            row.show_in_customer_quote = 0
        with self.assertRaises(frappe.ValidationError):
            export_workbook(doc, "customer")
