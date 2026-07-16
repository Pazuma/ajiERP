import frappe


def execute():
    """Restore the native English labels for receipt and delivery sidebar links."""
    for sidebar_name, doctype, label in (
        ("Buying", "Purchase Receipt", "Purchase Receipt"),
        ("Selling", "Delivery Note", "Delivery Note"),
    ):
        frappe.db.set_value(
            "Workspace Sidebar Item",
            {"parent": sidebar_name, "type": "Link", "link_type": "DocType", "link_to": doctype},
            "label",
            label,
        )
    frappe.clear_cache()
