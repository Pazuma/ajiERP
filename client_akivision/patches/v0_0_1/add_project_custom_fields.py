import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add technical domain and project leader custom fields to Project."""
    create_custom_fields(
        {
            "Project": [
                {
                    "fieldname": "custom_technical_domain",
                    "label": "Technical Domain",
                    "fieldtype": "Data",
                    "insert_after": "project_name",
                    "translatable": 0,
                },
                {
                    "fieldname": "custom_project_leader",
                    "label": "Project Leader",
                    "fieldtype": "Link",
                    "options": "User",
                    "insert_after": "custom_technical_domain",
                    "translatable": 0,
                },
            ]
        },
        update=True,
    )
    frappe.clear_cache()
