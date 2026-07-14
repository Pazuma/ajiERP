import frappe


def execute():
    """Fix the position of the Delivery Details tab on Purchase Order.

    The tab should sit after "customer_contact_email" so that all address/contact
    fields remain in the "Address & Contact" / "Drop Ship" tabs.
    """
    fieldname = "custom_cf_delivery_details_tab"
    if not frappe.db.exists("Custom Field", {"name": f"Purchase Order-{fieldname}"}):
        return

    frappe.db.set_value(
        "Custom Field",
        f"Purchase Order-{fieldname}",
        "insert_after",
        "customer_contact_email",
    )

    frappe.clear_cache(doctype="Purchase Order")
