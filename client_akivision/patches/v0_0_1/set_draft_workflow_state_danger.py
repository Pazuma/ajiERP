import frappe


def execute():
    """Render the draft state as a red danger indicator in the desk."""
    if frappe.db.exists("Workflow State", "Draft"):
        frappe.db.set_value("Workflow State", "Draft", "style", "Danger", update_modified=False)
        frappe.clear_cache(doctype="Workflow State")
    frappe.clear_cache(doctype="Engineering Drawing")
