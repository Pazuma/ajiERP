import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from client_akivision.utils import layered_manufacturing as flow


class TestLayeredManufacturing(unittest.TestCase):
    def test_new_order_uses_direct_components_when_company_enabled(self):
        doc = frappe._dict(company="Company", use_multi_level_bom=1, bom_no="BOM", qty=2)
        doc.is_new = lambda: True
        doc.get_doc_before_save = lambda: None
        calls = []
        doc.set_required_items = lambda: calls.append(doc.use_multi_level_bom)
        with patch.object(frappe.db, "get_value", return_value=1):
            flow.initialize_direct_component_work_order(doc)
        self.assertEqual(doc.custom_direct_component_supply, 1)
        self.assertEqual(doc.custom_layered_mode, 1)
        self.assertEqual(calls, [0])

    def test_existing_order_is_not_automatically_converted(self):
        doc = frappe._dict(company="Company", docstatus=1, use_multi_level_bom=1)
        doc.is_new = lambda: False
        with patch.object(frappe.db, "get_value") as value:
            flow.initialize_direct_component_work_order(doc)
        value.assert_not_called()
        self.assertEqual(doc.use_multi_level_bom, 1)

    def test_submitted_order_cannot_change_new_mode(self):
        doc = frappe._dict(custom_direct_component_supply=1)
        doc.get_doc_before_save = lambda: frappe._dict(docstatus=1, custom_direct_component_supply=0)
        with self.assertRaises(frappe.ValidationError):
            flow.validate_work_order(doc)

    def _direct_row(self, qty=6):
        return dict(item_code="B", warehouse="W", allocatable_qty=qty, links=[],
            supply_mode="可外购/可自制", bom_no="BOM-B", is_purchase_item=1)

    def _allocate_direct(self, decisions, row):
        wo = frappe._dict(name="WO", company="Company", custom_direct_component_supply=1)
        bom = frappe._dict(company="Company")
        bom.check_permission = lambda *args: None
        with patch.object(flow, "_entry", return_value=(None, wo)), patch.object(flow, "_shortages", return_value=[row]), \
                patch.object(frappe.db, "sql", return_value=[]), patch.object(frappe.db, "savepoint"), \
                patch.object(frappe, "get_doc", return_value=bom), patch.object(frappe, "has_permission", return_value=True), \
                patch.object(flow, "_allocate_shortage", return_value={"created": []}) as allocate:
            result = flow.allocate_direct_component_shortage({}, decisions)
            return result, allocate.call_args.args[2]

    def test_checked_only_manufactures_server_calculated_gap(self):
        _, selected = self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=True, manufacture_qty=999)], self._direct_row())
        self.assertEqual(selected, [dict(item_code="B", warehouse="W", purchase_qty=0, manufacture_qty=6)])

    def test_unchecked_only_purchases_semifinished_item(self):
        _, selected = self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=False)], self._direct_row())
        self.assertEqual(selected, [dict(item_code="B", warehouse="W", purchase_qty=6, manufacture_qty=0)])

    def test_already_allocated_gap_creates_nothing(self):
        _, selected = self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=True)], self._direct_row(qty=0))
        self.assertEqual(selected, [])

    def test_duplicate_new_decisions_rejected(self):
        decision = dict(item_code="B", warehouse="W", create_work_order=False)
        with self.assertRaises(frappe.ValidationError):
            self._allocate_direct([decision, decision], self._direct_row())

    def test_no_bom_cannot_manufacture(self):
        row = self._direct_row()
        row["bom_no"] = None
        with self.assertRaises(frappe.ValidationError):
            self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=True)], row)

    def test_old_allocation_api_cannot_bypass_direct_mode(self):
        with patch.object(flow, "_entry", return_value=(None, frappe._dict(custom_direct_component_supply=1))), self.assertRaises(frappe.ValidationError):
            flow.allocate_shortage({}, [])

    def test_item_defaults_ignore_legacy_bom_setting(self):
        wo = frappe._dict(custom_direct_component_supply=1)
        rows = [
            dict(item_code="MAKE", warehouse="W", bom_no="BOM-MAKE", supply_mode="自制"),
            dict(item_code="BUY", warehouse="W", bom_no="BOM-BUY", supply_mode="外购"),
            dict(item_code="RAW", warehouse="W", bom_no=None, supply_mode=None),
        ]
        with patch.object(flow, "_entry", return_value=(None, wo)), \
                patch.object(flow, "_shortages", return_value=rows), \
                patch.object(frappe.db, "get_value") as get_value:
            defaults = flow.get_direct_component_shortage_defaults({})
        get_value.assert_not_called()
        self.assertEqual([r["default_create_work_order"] for r in defaults["rows"]], [True, False, False])
        self.assertEqual([r["item_code"] for r in defaults["rows"]], ["MAKE", "BUY", "RAW"])
        self.assertTrue(all(r["warehouse"] == "W" for r in defaults["rows"]))
        self.assertTrue(all(r["default_source"] == "item_supply_mode" for r in defaults["rows"]))

    def test_item_default_matrix_and_missing_bom_warning(self):
        for mode in (None, "", "外购", "自制", "可外购/可自制"):
            for bom in (None, "BOM-B"):
                with self.subTest(mode=mode, bom=bom):
                    result = flow._get_item_shortage_default(dict(supply_mode=mode, bom_no=bom))
                    self.assertEqual(result["default_create_work_order"], bool(mode == "自制" and bom))
                    self.assertEqual(bool(result["default_block_reason"]), mode == "自制" and not bom)
                    self.assertEqual(result["supply_mode"], mode or "外购")

    def test_direct_mode_allows_deliberate_override_of_item_preference(self):
        for mode, make in (("自制", False), ("外购", True)):
            with self.subTest(mode=mode):
                row = self._direct_row()
                row["supply_mode"] = mode
                _, selected = self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=make)], row)
                self.assertEqual(selected[0]["manufacture_qty"], 6 if make else 0)
                self.assertEqual(selected[0]["purchase_qty"], 0 if make else 6)

    def test_direct_purchase_still_requires_purchase_item(self):
        row = self._direct_row()
        row["is_purchase_item"] = 0
        with self.assertRaises(frappe.ValidationError):
            self._allocate_direct([dict(item_code="B", warehouse="W", create_work_order=False)], row)

    def test_non_direct_mode_does_not_return_bom_defaults(self):
        with patch.object(flow, "_entry", return_value=(None, frappe._dict(custom_direct_component_supply=0))), \
                patch.object(flow, "_shortages") as shortages:
            self.assertEqual(flow.get_direct_component_shortage_defaults({}), {"rows": []})
        shortages.assert_not_called()

    def test_tree_keeps_paths_and_scales_bom_output_quantity(self):
        wo = frappe._dict(name="WO", bom_no="ROOT", qty=10, company="Company", required_items=["unchanged"])
        wo.check_permission = lambda *args: None
        root = SimpleNamespace(docstatus=1, is_active=1, quantity=2, company="Company",
            items=[frappe._dict(idx=1, item_code="B", stock_qty=3, stock_uom="Nos", bom_no="CHILD")])
        child = SimpleNamespace(docstatus=1, is_active=1, quantity=5, company="Company",
            items=[frappe._dict(idx=1, item_code="C", stock_qty=2, stock_uom="Nos")])
        for bom in (root, child):
            bom.check_permission = lambda *args: None
        with patch.object(frappe, "get_doc", side_effect=lambda dt, name: {"WO": wo, "ROOT": root, "CHILD": child}[name]), patch.object(frappe.db, "get_value", return_value="B"):
            data = flow.get_work_order_component_tree("WO")
        self.assertEqual([r["required_qty"] for r in data["rows"]], [15, 6])
        self.assertEqual([r["depth"] for r in data["rows"]], [1, 2])
        self.assertEqual(wo.required_items, ["unchanged"])

    def test_old_mode_is_unchanged(self):
        doc = frappe._dict(custom_layered_mode=0)
        doc.get_doc_before_save = lambda: None
        flow.validate_work_order(doc)

    def test_direct_bom_required(self):
        doc = frappe._dict(custom_layered_mode=1, company="test", track_semi_finished_goods=0, use_multi_level_bom=1)
        doc.get_doc_before_save = lambda: None
        with patch.object(frappe.db, "get_value", return_value=1), self.assertRaises(frappe.ValidationError):
            flow.validate_work_order(doc)

    def test_duplicate_rows_use_combined_stock_need(self):
        wo = frappe._dict(name="WO", company="Company", required_items=[frappe._dict(item_code="B", required_qty=200)])
        doc = SimpleNamespace(posting_date="2026-10-10", posting_time="10:00:00", items=[
            frappe._dict(item_code="B", s_warehouse="Warehouse", qty=60, conversion_factor=1),
            frappe._dict(item_code="B", s_warehouse="Warehouse", qty=40, conversion_factor=1)])
        def value(doctype, *args, **kwargs):
            if doctype == "Warehouse": return "Company"
            return frappe._dict(item_name="B", stock_uom="Nos", custom_supply_mode="可外购/可自制", default_bom="BOM-B", is_purchase_item=1)
        with patch.object(frappe.db, "get_value", side_effect=value), patch.object(frappe.db, "exists", return_value=True), patch.object(flow, "_pending", return_value=(20, [])), patch("erpnext.stock.utils.get_stock_balance", return_value=40):
            rows = flow._shortages(doc, wo)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shortage_qty"], 60)
        self.assertEqual(rows[0]["allocatable_qty"], 40)
        self.assertEqual(rows[0]["available_qty"], 40)

    def test_overallocation_rejected(self):
        wo = frappe._dict(name="WO")
        row = dict(item_code="B", warehouse="W", allocatable_qty=60)
        with patch.object(flow, "_entry", return_value=(None, wo)), patch.object(flow, "_shortages", return_value=[row]), patch.object(frappe.db, "sql", return_value=[]), self.assertRaises(frappe.ValidationError):
            flow.allocate_shortage({}, [dict(item_code="B", warehouse="W", purchase_qty=40, manufacture_qty=40)])

    def test_purchase_only_cannot_manufacture(self):
        wo = frappe._dict(name="WO")
        row = dict(item_code="B", warehouse="W", allocatable_qty=60, supply_mode="外购", bom_no="BOM-B", is_purchase_item=1)
        with patch.object(flow, "_entry", return_value=(None, wo)), patch.object(flow, "_shortages", return_value=[row]), patch.object(frappe.db, "sql", return_value=[]), self.assertRaises(frappe.ValidationError):
            flow.allocate_shortage({}, [dict(item_code="B", warehouse="W", manufacture_qty=60)])

    def test_inspection_cannot_be_reused_above_accepted_qty(self):
        doc = frappe._dict(work_order="WO", purpose="Manufacture", custom_quality_inspection="QI", fg_completed_qty=4, name="SE", inspection_required=1)
        qi = frappe._dict(name="QI", docstatus=1, status="Accepted", custom_work_order="WO", custom_accepted_qty=10)
        with patch.object(flow, "is_layered", return_value=True), patch.object(frappe, "get_doc", return_value=qi), patch.object(frappe.db, "sql", side_effect=[[], [(8,)]]), self.assertRaises(frappe.ValidationError):
            flow.validate_stock_entry(doc)
