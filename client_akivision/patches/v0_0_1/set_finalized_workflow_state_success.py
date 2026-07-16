import frappe


def execute():
    """Render the finalized state as a green success indicator in the desk."""
    if frappe.db.exists("Workflow State", "Finalized"):
        frappe.db.set_value("Workflow State", "Finalized", "style", "Success", update_modified=False)
        frappe.clear_cache(doctype="Workflow State")
    frappe.clear_cache(doctype="Engineering Drawing")
