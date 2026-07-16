import frappe

from client_akivision.patches.v0_0_1.add_engineering_drawing_custom_fields import execute as create_fields


def execute():
    """Add traceability fields on existing sites and make legacy drawings usable."""
    create_fields()
    if not frappe.db.table_exists("Engineering Drawing"):
        return

    frappe.db.sql(
        """
        UPDATE `tabEngineering Drawing`
        SET drawing_no = name
        WHERE IFNULL(drawing_no, '') = ''
        """
    )
    frappe.db.sql(
        """
        UPDATE `tabItem` item
        INNER JOIN `tabEngineering Drawing` drawing ON drawing.name = item.custom_engineering_drawing
        SET item.custom_engineering_drawing_no = drawing.drawing_no,
            item.custom_engineering_drawing_revision = drawing.revision
        WHERE drawing.status = 'Finalized'
        """
    )
    frappe.db.sql(
        """
        UPDATE `tabBOM` bom
        INNER JOIN `tabEngineering Drawing` drawing ON drawing.name = bom.custom_engineering_drawing
        SET bom.custom_engineering_drawing_no = drawing.drawing_no,
            bom.custom_engineering_drawing_revision = drawing.revision
        WHERE drawing.status = 'Finalized'
        """
    )
    frappe.clear_cache()
