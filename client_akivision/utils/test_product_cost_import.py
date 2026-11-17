from io import BytesIO
import unittest

import frappe
from openpyxl import load_workbook

from client_akivision.utils.product_cost_import import parse, workbook
from client_akivision.utils.test_product_cost_sources import draft
from client_akivision.api.product_cost_quotation_import import preview_import, apply_import


class TestProductCostImport(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.savepoint("pcq_exchange_test")

    def tearDown(self):
        frappe.db.rollback(save_point="pcq_exchange_test")

    def test_roundtrip_and_source_protection(self):
        doc = draft().insert()
        result = parse(workbook(doc, "internal"), doc)
        self.assertFalse(result["errors"])
        self.assertFalse(result["changes"])
        doc.materials[0].source_key = "BOM:protected"
        book = load_workbook(BytesIO(workbook(doc, "internal")))
        book["materials"].append([doc.materials[0].name, None, "forbidden"])
        output = BytesIO()
        book.save(output)
        self.assertTrue(any("来源行" in e for e in parse(output.getvalue(), doc)["errors"]))

    def test_preview_apply_and_concurrency(self):
        doc = draft().insert()
        book = load_workbook(BytesIO(workbook(doc, "internal")))
        sheet = book["scenarios"]
        headers = [c.value for c in sheet[1]]
        sheet.cell(2, headers.index("final_tax_inclusive_price") + 1, 220)
        sheet.cell(2, headers.index("price_override_reason") + 1, "导入调价依据")
        output = BytesIO()
        book.save(output)
        file = frappe.get_doc({"doctype": "File", "file_name": "pcq-test.xlsx", "is_private": 1, "content": output.getvalue()}).insert()
        preview = preview_import(doc.name, file.file_url, str(doc.modified))
        self.assertFalse(preview["errors"])
        apply_import(doc.name, preview["preview_id"], str(doc.modified), ["scenarios"])
        doc.reload()
        self.assertEqual(doc.scenarios[0].final_tax_inclusive_price, 220)
        with self.assertRaises(frappe.ValidationError):
            apply_import(doc.name, preview["preview_id"], str(doc.modified), ["scenarios"])

    def test_formula_and_wrong_product_rejected(self):
        doc = draft().insert()
        book = load_workbook(BytesIO(workbook(doc, "internal")))
        book["main"]["A2"] = "=1+1"
        output = BytesIO()
        book.save(output)
        self.assertTrue(parse(output.getvalue(), doc)["errors"])
        book["说明"]["B4"] = "wrong-product"
        output = BytesIO()
        book.save(output)
        with self.assertRaises(frappe.ValidationError):
            parse(output.getvalue(), doc)

    def test_persisted_source_context_blocks_old_product(self):
        doc = draft()
        doc.materials[0].source_key = "BOM:source-context-test"
        doc.insert()
        doc.item_code = frappe.get_list("Item", pluck="name", limit_page_length=1)[0]
        doc.save()
        doc.reload()
        with self.assertRaises(frappe.ValidationError):
            doc.check_source_context()
