import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Supplier": [
                {
                    "fieldname": "custom_rating_standard",
                    "label": "Rating Standard",
                    "fieldtype": "Link",
                    "options": "Supplier Rating Standard",
                    "insert_after": "custom_supplier_rating",
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.db.updatedb("Supplier")
    frappe.clear_cache(doctype="Supplier")
