import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Store the per-supplier quote column mapping remembered by Supplier Quote Import."""
    create_custom_fields(
        {
            "Supplier": [
                {
                    "fieldname": "custom_quote_column_mapping",
                    "label": "Quote Column Mapping",
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
