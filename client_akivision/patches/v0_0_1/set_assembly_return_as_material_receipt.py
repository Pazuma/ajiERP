import frappe


def execute():
    """Set assembly return to Material Receipt without touching historical entries."""
    entry_type = "组装退料"
    if not frappe.db.exists("Stock Entry Type", entry_type):
        return

    frappe.db.set_value("Stock Entry Type", entry_type, "purpose", "Material Receipt")
    frappe.clear_cache()
