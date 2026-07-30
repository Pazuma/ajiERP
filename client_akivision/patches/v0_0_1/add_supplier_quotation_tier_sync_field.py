import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Track the tier-price sync status on Supplier Quotation."""
    create_custom_fields(
        {
            "Supplier Quotation": [
                {
                    "fieldname": "custom_tier_sync_status",
                    "label": "Tier Sync",
                    "fieldtype": "Select",
                    "options": "\nSynced\nSync Failed",
                    "read_only": 1,
                    "insert_after": "valid_till",
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Supplier Quotation")
