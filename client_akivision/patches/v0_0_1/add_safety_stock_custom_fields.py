import frappe


def execute():
    """Add custom fields for safety stock parameters."""
    create_item_reorder_custom_fields()
    create_item_custom_fields()


def create_item_reorder_custom_fields():
    """Add maximum stock limit to Item Reorder child table."""
    if not frappe.db.exists(
        "Custom Field", {"dt": "Item Reorder", "fieldname": "custom_max_stock_limit"}
    ):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Item Reorder",
                "fieldname": "custom_max_stock_limit",
                "label": "Maximum Stock Limit",
                "fieldtype": "Float",
                "non_negative": 1,
                "insert_after": "material_request_type",
                "in_list_view": 1,
            }
        ).insert()


def create_item_custom_fields():
    """Add safety stock remarks to Item master."""
    if not frappe.db.exists(
        "Custom Field", {"dt": "Item", "fieldname": "custom_safety_stock_remarks"}
    ):
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": "Item",
                "fieldname": "custom_safety_stock_remarks",
                "label": "Safety Stock Remarks",
                "fieldtype": "Small Text",
                "insert_after": "safety_stock",
            }
        ).insert()

    frappe.clear_cache()
