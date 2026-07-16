import frappe


def execute():
    """Add a header-level Remarks custom field to Sales Order and Delivery Note."""
    for dt, insert_after in (
        ("Sales Order", "additional_info_section"),
        ("Delivery Note", "more_info"),
    ):
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": "custom_remarks"}):
            continue
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": dt,
                "fieldname": "custom_remarks",
                "label": "Remarks",
                "fieldtype": "Data",
                "insert_after": insert_after,
                "allow_on_submit": 1,
                "translatable": 0,
            }
        ).insert()
    frappe.clear_cache()
