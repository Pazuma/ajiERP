import frappe


def execute():
    """Move the custom purchase order link field from More Info to the Details section."""
    fieldname = "Purchase Receipt-custom_purchase_order"
    if not frappe.db.exists("Custom Field", fieldname):
        return

    cf = frappe.get_doc("Custom Field", fieldname)
    cf.insert_after = "supplier_name"
    cf.save()
    frappe.clear_cache(doctype="Purchase Receipt")
