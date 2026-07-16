import frappe


def execute():
    """Add custom fields for sales order high-tech revenue tracking."""
    create_sales_order_custom_fields()
    frappe.db.updatedb("Sales Order")
    frappe.clear_cache()


def create_sales_order_custom_fields():
    """Add high-tech revenue flag to Sales Order and Sales Order Item."""
    if not frappe.db.exists(
        "Custom Field", {"dt": "Sales Order", "fieldname": "custom_is_high_tech_revenue"}
    ):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Sales Order",
                "fieldname": "custom_is_high_tech_revenue",
                "label": "High-tech Revenue",
                "fieldtype": "Check",
                "insert_after": "order_type",
                "default": "0",
                "allow_on_submit": 1,
            }
        ).insert()
