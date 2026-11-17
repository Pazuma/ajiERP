import frappe
from frappe.tests import IntegrationTestCase
from client_akivision.utils.bom_version import create_update_version, activate_bom_version, switch_draft_work_order_bom


class TestBOMVersion(IntegrationTestCase):
    def test_version_lifecycle(self):
        source_name = frappe.db.get_value("BOM", {"docstatus": 1, "is_active": 1, "is_default": 1}, "name")
        self.assertTrue(source_name)
        source = frappe.get_doc("BOM", source_name)
        original_items = [(r.item_code, r.qty, r.bom_no) for r in source.items]
        original_wos = frappe.get_all("Work Order", filters={"bom_no": source_name}, pluck="name")
        from erpnext.manufacturing.doctype.work_order.work_order import make_work_order
        wo = frappe.get_doc(make_work_order(source_name, source.item, qty=source.quantity, company=source.company))
        wo.insert()
        original_wos.append(wo.name)
        name = create_update_version(source_name)
        self.assertEqual(name, create_update_version(source_name))
        draft = frappe.get_doc("BOM", name)
        self.assertEqual(draft.docstatus, 0)
        self.assertEqual(draft.custom_version_source, source_name)
        self.assertFalse(draft.amended_from)
        self.assertEqual(original_items, [(r.item_code, r.qty, r.bom_no) for r in draft.items])
        self.assertEqual(frappe.db.get_value("Item", source.item, "default_bom"), source_name)
        draft.items[0].qty *= 2
        draft.custom_bom_code = "MANUAL-" + source.custom_bom_code
        from client_akivision.client_akivision.api.bom import preview_bom_draft
        preview = preview_bom_draft(draft.as_json())
        self.assertEqual(preview["items"][1]["qty"], draft.items[0].qty)
        self.assertEqual(preview["items"][0]["drawing_no"], draft.custom_bom_code)
        self.assertEqual(frappe.get_doc("BOM", name).items[0].qty, original_items[0][1])
        forged = source.as_dict()
        forged.docstatus = 0
        with self.assertRaises(frappe.ValidationError):
            preview_bom_draft(frappe.as_json(forged))
        draft.save()
        draft.reload()
        self.assertEqual(draft.custom_bom_code, "MANUAL-" + source.custom_bom_code)
        from client_akivision.client_akivision.api.bom import get_bom_list_entries
        entries = get_bom_list_entries()
        self.assertIn(source_name, entries)
        self.assertNotIn(name, entries)
        self.assertEqual(frappe.db.get_value("Item", source.item, "default_bom"), source_name)
        activate_bom_version(name)
        from client_akivision.client_akivision.api.bom import get_bom_version_view
        activated = frappe.get_doc("BOM", name)
        self.assertTrue(activated.custom_first_activated_at)
        view = get_bom_version_view(source_name, name)
        self.assertTrue(view["summary"]["is_current_default"])
        self.assertEqual(view["items"][0]["drawing_no"], activated.custom_bom_code)
        self.assertEqual(view["items"][0]["item_name"], frappe.db.get_value("Item", source.item, "custom_internal_model") or "")
        entries = get_bom_list_entries()
        self.assertIn(name, entries)
        self.assertNotIn(source_name, entries)
        self.assertEqual(set(view["items"][0]), {"model", "level", "item_name", "drawing_no", "qty"})
        self.assertEqual(view["items"][1]["qty"], draft.items[0].qty)
        activated.custom_first_activated_at = None
        with self.assertRaises(frappe.ValidationError):
            activated.save()
        source.reload()
        self.assertEqual(source.docstatus, 1)
        self.assertTrue(source.is_active)
        self.assertFalse(source.is_default)
        self.assertEqual(frappe.db.get_value("Item", source.item, "default_bom"), name)
        self.assertEqual(original_wos, frappe.get_all("Work Order", filters={"bom_no": source_name}, pluck="name"))
        self.assertEqual(original_items, [(r.item_code, r.qty, r.bom_no) for r in source.items])
        switch_draft_work_order_bom(wo.name, name)
        wo.reload()
        self.assertEqual(wo.bom_no, name)
        self.assertTrue(wo.required_items)
        stale = create_update_version(source_name)
        with self.assertRaises(frappe.ValidationError):
            activate_bom_version(stale)

    def test_no_permission_to_create(self):
        source = frappe.db.get_value("BOM", {"docstatus": 1, "is_active": 1}, "name")
        user = frappe.session.user
        try:
            frappe.set_user("Guest")
            with self.assertRaises(frappe.PermissionError):
                create_update_version(source)
            from client_akivision.client_akivision.api.bom import get_bom_version_view
            with self.assertRaises(frappe.PermissionError):
                get_bom_version_view(source, source)
        finally:
            frappe.set_user(user)

    def test_submitted_work_order_cannot_switch(self):
        name = frappe.db.get_value("Work Order", {"docstatus": 1}, "name")
        self.assertTrue(name)
        wo = frappe.get_doc("Work Order", name)
        with self.assertRaises(frappe.ValidationError):
            switch_draft_work_order_bom(name, wo.bom_no)
