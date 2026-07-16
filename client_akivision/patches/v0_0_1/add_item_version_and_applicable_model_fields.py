import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Provide the Item master fields consumed by receipt list reports."""
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_internal_model",
                    "label": "Internal Model",
                    "fieldtype": "Data",
                    "insert_after": "item_name",
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_applicable_model",
                    "label": "Applicable Model",
                    "fieldtype": "Data",
                    "insert_after": "custom_internal_model",
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_version",
                    "label": "Version",
                    "fieldtype": "Data",
                    "insert_after": "custom_external_model",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Item")
