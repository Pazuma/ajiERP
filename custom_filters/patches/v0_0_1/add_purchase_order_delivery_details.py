import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add Purchase Order delivery details tab and HTML field under Custom Filters."""
    create_custom_fields(
        {
            "Purchase Order": [
                {
                    "fieldname": "custom_cf_delivery_details_tab",
                    "label": "交货详情",
                    "fieldtype": "Tab Break",
                    "insert_after": "customer_contact_email",
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_cf_delivery_details",
                    "label": "交货详情报表",
                    "fieldtype": "HTML",
                    "insert_after": "custom_cf_delivery_details_tab",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )

    # Remove old client_akivision fields if they exist.
    for old_fieldname in [
        "custom_akivision_delivery_details_tab",
        "custom_akivision_delivery_details",
    ]:
        full_name = f"Purchase Order-{old_fieldname}"
        if frappe.db.exists("Custom Field", full_name):
            frappe.delete_doc("Custom Field", full_name, force=1)

    frappe.clear_cache(doctype="Purchase Order")
