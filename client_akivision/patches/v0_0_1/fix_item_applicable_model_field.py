import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Separate applicable model from the existing internal model field."""
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
            ]
        },
        update=True,
    )
    frappe.db.updatedb("Item")
    frappe.clear_cache(doctype="Item")
