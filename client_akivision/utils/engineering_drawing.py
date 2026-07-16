import frappe
from frappe import _


def validate_bom_drawing(doc, method=None):
    drawing_name = doc.get("custom_engineering_drawing")
    if drawing_name:
        drawing = frappe.db.get_value("Engineering Drawing", drawing_name, ["status", "drawing_no", "revision"], as_dict=True)
        if not drawing or drawing.status != "Finalized":
            frappe.throw(_("BOM 只能关联已定稿图纸。"))
        doc.custom_engineering_drawing_revision = drawing.revision
        doc.custom_engineering_drawing_no = drawing.drawing_no
    snapshot_component_drawings(doc)


def snapshot_component_drawings(doc):
    """Snapshot each component item's current finalized drawing onto its BOM row."""
    item_codes = {row.item_code for row in doc.get("items", []) if row.item_code}
    if not item_codes:
        return
    items = {
        row.name: row
        for row in frappe.get_all(
            "Item",
            filters={"name": ["in", list(item_codes)]},
            fields=["name", "custom_engineering_drawing", "custom_engineering_drawing_no", "custom_engineering_drawing_revision"],
        )
    }
    for row in doc.get("items", []):
        item = items.get(row.item_code)
        if not item or not item.custom_engineering_drawing:
            row.custom_engineering_drawing = None
            row.custom_engineering_drawing_no = None
            row.custom_engineering_drawing_revision = None
            continue

        drawing_status = frappe.db.get_value("Engineering Drawing", item.custom_engineering_drawing, "status")
        if drawing_status != "Finalized":
            frappe.throw(_("组件物料 {0} 引用的图纸未定稿，不能用于 BOM。").format(row.item_code))
        row.custom_engineering_drawing = item.custom_engineering_drawing
        row.custom_engineering_drawing_no = item.custom_engineering_drawing_no
        row.custom_engineering_drawing_revision = item.custom_engineering_drawing_revision


def set_material_request_drawing_reference(doc, method=None):
    bom_names = {row.bom_no for row in doc.get("items", []) if row.bom_no}
    if len(bom_names) != 1:
        return
    _set_drawing_reference_from_bom(doc, bom_names.pop())


def set_work_order_drawing_reference(doc, method=None):
    if doc.get("bom_no"):
        _set_drawing_reference_from_bom(doc, doc.bom_no)


def _set_drawing_reference_from_bom(doc, bom_name):
    drawing = frappe.db.get_value(
        "BOM", bom_name, ["custom_engineering_drawing", "custom_engineering_drawing_no", "custom_engineering_drawing_revision"], as_dict=True
    )
    if drawing and drawing.custom_engineering_drawing:
        doc.custom_engineering_drawing = drawing.custom_engineering_drawing
        doc.custom_engineering_drawing_no = drawing.custom_engineering_drawing_no
        doc.custom_engineering_drawing_revision = drawing.custom_engineering_drawing_revision
