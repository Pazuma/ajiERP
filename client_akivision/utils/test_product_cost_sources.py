"""Run with a connected test site; all created quotation records roll back."""
import json
import unittest
from unittest.mock import patch

import frappe

from client_akivision.api.product_cost_quotation import (apply_source_refresh, get_line_detail,
    get_source_context, preview_calculation, preview_source_refresh)
from client_akivision.utils.product_cost_sources import _expand_bom, work_order_reference, _project_investments
from client_akivision.utils.product_cost_permissions import has_permission


def draft():
    company = frappe.get_list("Company", pluck="name", limit_page_length=1)[0]
    currency = frappe.get_cached_value("Company", company, "default_currency")
    return frappe.get_doc({"doctype": "Product Cost Quotation", "company": company, "currency": currency,
                           "exchange_rate": 1, "provisional_model": "PCQ-自动验收-不保留",
                           "tax_rate": 13, "target_margin": 40, "cost_ratio": 40, "pricing_method": "Target Margin",
                           "materials": [{"description": "临时材料", "qty_per_unit": 3, "conversion_factor": 1,
                                          "price_basis": "Manual", "manual_rate": 10, "price_currency": currency,
                                          "price_exchange_rate": 1, "tax_basis": "Exclusive", "pack_multiple": 1,
                                          "manual_reason": "验收用价格"}],
                           "operations": [{"operation": "组装", "charging_basis": "Per Unit", "standard_hours": 1,
                                           "hourly_rate": 80, "included_cost_scope": "人工", "manual_reason": "验收标准工时"}],
                           "scenarios": [{"quantity": q} for q in (50, 100, 200, 500)]})


class TestProductCostSources(unittest.TestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.savepoint("pcq_test")

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback(save_point="pcq_test")

    def test_save_calculate_submit_snapshot_and_revision(self):
        doc = draft().insert()
        self.assertAlmostEqual(doc.scenarios[0].full_unit_cost, 110)
        detail = get_line_detail(doc.name, doc.materials[0].name)
        self.assertEqual(len(detail["calculations"]), 4)
        self.assertEqual(len(preview_calculation(doc.name, str(doc.modified))), 4)
        doc.estimate_acknowledged = 1
        doc.estimate_reason = "确认手工材料价格、税务口径、人工范围"
        doc.submit()
        saved_hash = doc.snapshot_hash
        frozen = frappe.get_doc(doc.doctype, doc.name)
        self.assertEqual(frozen.snapshot_hash, saved_hash)
        with self.assertRaises(frappe.ValidationError):
            apply_source_refresh(doc.name, str(doc.modified), ["materials"])
        revision = frappe.copy_doc(doc)
        revision.docstatus = 0
        revision.previous_version = doc.name
        revision.estimate_acknowledged = 0
        revision.insert()
        self.assertEqual(revision.docstatus, 0)
        self.assertEqual(revision.previous_version, doc.name)

    def test_missing_price_cannot_submit(self):
        doc = draft()
        doc.materials[0].manual_rate = 0
        doc.insert()
        self.assertEqual(doc.scenarios[0].completeness, "Incomplete")
        doc.estimate_acknowledged = 1
        doc.estimate_reason = "test"
        with self.assertRaises(frappe.ValidationError):
            doc.submit()

    def test_refresh_preserves_manual_rows_and_concurrency(self):
        doc = draft().insert()
        preview = preview_source_refresh(doc.name)
        self.assertEqual(preview["groups"][0]["new_count"], 0)
        with self.assertRaises(frappe.TimestampMismatchError):
            apply_source_refresh(doc.name, "2000-01-01", ["materials"])
        apply_source_refresh(doc.name, str(doc.modified), ["materials"])
        doc.reload()
        self.assertEqual(len(doc.materials), 1)
        self.assertEqual(doc.materials[0].manual_reason, "验收用价格")

    def test_foreign_child_rejected(self):
        a = draft().insert()
        b = draft().insert()
        with self.assertRaises(frappe.PermissionError):
            get_line_detail(a.name, b.materials[0].name)

    def test_guest_cannot_read(self):
        doc = draft().insert()
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            get_line_detail(doc.name, doc.materials[0].name)

    def test_controller_permission_continues_standard_role_check(self):
        doc = draft()
        self.assertTrue(has_permission(doc, ptype="create", user="Administrator"))
        self.assertFalse(has_permission(doc, ptype="read", user="Guest"))
        self.assertTrue(frappe.has_permission("Product Cost Quotation", "create", user="Administrator"))
        self.assertFalse(frappe.has_permission("Product Cost Quotation", "read", user="Guest"))

    def test_three_existing_entry_contexts_are_read_only(self):
        for dt in ("Item", "Project", "Work Order"):
            names = frappe.get_list(dt, pluck="name", limit_page_length=1)
            if not names:
                continue
            before = frappe.db.get_value(dt, names[0], "modified")
            context = get_source_context(dt, names[0])
            self.assertEqual(context["source_type"], dt)
            self.assertEqual(frappe.db.get_value(dt, names[0], "modified"), before)

    def test_recursive_bom_and_cycle(self):
        def d(**values):
            return frappe._dict(values)
        boms = {"root": d(quantity=2, items=[d(name="a", item_code="sub", stock_qty=4, bom_no="sub"),
                                            d(name="b", item_code="part", stock_qty=2)], operations=[]),
                "sub": d(quantity=1, items=[d(name="c", item_code="part", stock_qty=3)], operations=[])}
        def read(dt, name, *args):
            return boms[name] if dt == "BOM" else d(item_name=name, stock_uom="Nos", item_group="五金")
        with patch("client_akivision.utils.product_cost_sources.read_source", side_effect=read):
            rows, _ = _expand_bom("root", "Company")
            self.assertEqual(sum(r["qty_per_unit"] for r in rows), 7)
            boms["sub"]["items"][0].bom_no = "root"
            with self.assertRaises(frappe.ValidationError):
                _expand_bom("root", "Company")

    def test_work_order_material_returns_reduce_reference_and_labor_is_not_readded(self):
        order = frappe._dict({"name": "WO-TEST", "status": "Completed", "produced_qty": 10, "qty": 10,
                              "custom_actual_labor_hours": 20, "custom_actual_labor_cost": 500,
                              "actual_operating_cost": 800})
        issue = frappe._dict({"name": "SE-ISSUE", "purpose": "Material Consumption for Manufacture", "is_return": 0,
                              "items": [frappe._dict(s_warehouse="Stores", basic_amount=1000, is_finished_item=0, is_scrap_item=0)]})
        returned = frappe._dict({"name": "SE-RETURN", "purpose": "Material Consumption for Manufacture", "is_return": 1,
                                 "items": [frappe._dict(s_warehouse="Stores", basic_amount=200, is_finished_item=0, is_scrap_item=0)]})
        def get_list(doctype, **kwargs):
            if doctype == "Stock Entry" and kwargs["filters"]["purpose"] == "Material Consumption for Manufacture":
                return ["SE-ISSUE", "SE-RETURN"]
            return []  # Dedicated issue vouchers exist, so don't read Manufacture lines again.
        with patch("client_akivision.utils.product_cost_sources.read_source", side_effect=lambda dt, name, *a: order if dt == "Work Order" else {"SE-ISSUE": issue, "SE-RETURN": returned}[name]), \
             patch("client_akivision.utils.product_cost_sources.frappe.get_list", side_effect=get_list), \
             patch("client_akivision.utils.product_cost_sources.frappe.get_cached_value", return_value="CNY"):
            result = work_order_reference("WO-TEST", "Company")
        self.assertEqual(result["actual_material_reference"], 800)
        self.assertEqual(result["actual_labor_cost"], 500)
        self.assertEqual(result["actual_operating_cost"], 800)
        self.assertIn("不再累加", result["note"])

    def test_project_cost_rows_and_timesheets_are_added_once_budget_stays_reference(self):
        class Meta:
            def has_field(self, field):
                return True
        project = frappe._dict({"name": "PROJ-TEST", "meta": Meta(),
                                "custom_project_cost_details": [frappe._dict(name="COST-1", cost_type="测试费", expense_description="验证", amount=1000)],
                                "custom_project_budget_details": [frappe._dict(name="BUDGET-1", expense_category="人员人工费", amount=9000)]})
        project.has_permlevel_access_to = lambda _field: True
        timesheet = frappe._dict({"name": "TS-TEST", "meta": Meta(), "time_logs": [frappe._dict(name="TIME-1", project="PROJ-TEST", activity_type="研发", base_costing_amount=2000)]})
        def read(dt, name, *args):
            return project if dt == "Project" else timesheet
        with patch("client_akivision.utils.product_cost_sources.read_source", side_effect=read), \
             patch("client_akivision.utils.product_cost_sources.frappe.get_list", return_value=["TS-TEST"]), \
             patch("client_akivision.utils.product_cost_sources.frappe.has_permission", return_value=True), \
             patch("client_akivision.utils.project_permissions.require_project_finance"):
            rows = _project_investments("PROJ-TEST", frappe._dict(company="Company", exchange_rate=1, investments=[]))
        actuals = [row["actual_amount"] for row in rows if row.get("actual_amount")]
        budgets = [row["budget_reference"] for row in rows if row.get("budget_reference")]
        self.assertEqual(actuals, [1000, 2000])
        self.assertEqual(budgets, [9000])
        self.assertEqual(len({row["source_key"] for row in rows}), len(rows))
