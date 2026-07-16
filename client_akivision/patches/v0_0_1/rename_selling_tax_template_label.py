import frappe


def execute():
    """Rename Selling sidebar Tax Template link to Sales Taxes and Charges Template."""
    frappe.db.set_value(
        "Workspace Sidebar Item",
        {
            "parent": "Selling",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Sales Taxes and Charges Template",
        },
        "label",
        "Sales Taxes and Charges Template",
    )
    frappe.clear_cache()
