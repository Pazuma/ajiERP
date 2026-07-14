import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Sales Order": [
                {
                    "fieldname": "custom_cf_shipment_details_tab",
                    "label": "出货明细",
                    "fieldtype": "Tab Break",
                    "insert_after": "terms",
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_cf_shipment_details",
                    "label": "出货明细报表",
                    "fieldtype": "HTML",
                    "insert_after": "custom_cf_shipment_details_tab",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Sales Order")
