import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Store the per-supplier "part number -> Item" memory used by Supplier Quote Import."""
    create_custom_fields(
        {
            "Supplier": [
                {
                    "fieldname": "custom_quote_item_mapping",
                    "label": "Quote Item Mapping",
                    "fieldtype": "JSON",
                    "hidden": 1,
                    "read_only": 1,
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Supplier")
