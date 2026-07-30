import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Link Purchase Orders back to the Purchase Comparison that generated them."""
    create_custom_fields(
        {
            "Purchase Order": [
                {
                    "fieldname": "custom_purchase_comparison",
                    "label": "Purchase Comparison",
                    "fieldtype": "Link",
                    "options": "Purchase Comparison",
                    "read_only": 1,
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Purchase Order")
