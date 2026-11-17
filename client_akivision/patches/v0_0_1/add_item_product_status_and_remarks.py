import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add product status and general remarks to the Item master."""
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_product_status",
                    "label": "Product Status",
                    "fieldtype": "Select",
                    # Keep the select values identical to the values used by
                    # the 产品清单 worksheet.  Data Import validates Select
                    # values literally, so English workflow labels here would
                    # reject the source values 开发/已量产/已打样.
                    "options": "\n开发\n已量产\n已打样",
                    "insert_after": "custom_applicable_model",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "translatable": 1,
                },
                {
                    "fieldname": "custom_remarks",
                    "label": "Remarks",
                    "fieldtype": "Small Text",
                    "insert_after": "description",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Item")
