import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add product status and general remarks to the Item master."""
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_product_status",
                    "label": "Product Status",
                    "fieldtype": "Select",
                    "options": "\nDevelopment\nMass Produced\nSampled",
                    "insert_after": "custom_applicable_model",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "translatable": 1,
                },
                {
                    "fieldname": "custom_remarks",
                    "label": "Remarks",
                    "fieldtype": "Small Text",
                    "insert_after": "description",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Item")
