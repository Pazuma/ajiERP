import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Default warehouse used for supplier quotations and comparison PO drafts."""
    create_custom_fields(
        {
            "Buying Settings": [
                {
                    "fieldname": "custom_supplier_quotation_warehouse",
                    "label": "Supplier Quotation Warehouse",
                    "fieldtype": "Link",
                    "options": "Warehouse",
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Buying Settings")
