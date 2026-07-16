import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Supplier": [
                {
                    "fieldname": "custom_supplier_rating",
                    "label": "Supplier Rating",
                    "fieldtype": "Data",
                    "insert_after": "prevent_pos",
                    "read_only": 1,
                    "translatable": 0,
                }
            ]
        }
    )
