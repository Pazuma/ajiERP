import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_cf_purchase_pricing_html",
                    "fieldtype": "HTML",
                    "label": "供应商采购阶梯价",
                    "insert_after": "supplier_items",
                    "translatable": 0,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Item")
