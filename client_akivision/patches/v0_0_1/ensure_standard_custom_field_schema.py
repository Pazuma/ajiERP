import frappe


STANDARD_DOCTYPES_WITH_CLIENT_FIELDS = (
    "Item",
    "Item Reorder",
    "Serial No",
    "Stock Entry",
    "Supplier",
    "Sales Order",
    "Delivery Note",
    "Purchase Receipt",
    "BOM",
    "BOM Item",
    "Material Request",
    "Work Order",
    "Project",
)


def execute():
    """Synchronize physical columns for Custom Fields created by this app."""
    for doctype in STANDARD_DOCTYPES_WITH_CLIENT_FIELDS:
        if not frappe.db.exists("Custom Field", {"dt": doctype}):
            continue
        frappe.db.updatedb(doctype)
        frappe.clear_cache(doctype=doctype)
