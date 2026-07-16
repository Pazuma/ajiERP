import frappe


STOCK_ENTRY_TYPE_PURPOSES = {
    "组装领料": "Material Issue",
    "组装退料": "Material Receipt",
    "生产补料": "Material Issue",
    "外发领料": "Send to Subcontractor",
    "产线借用": "Material Issue",
    "其它领用": "Material Issue",
    "Sample Loan In": "Material Receipt",
    "Sample Loan In Return": "Material Issue",
    "Sample Loan Out": "Material Transfer",
    "Sample Loan Out Return": "Material Transfer",
}


def execute():
    """Synchronize custom movement-type purposes; existing Stock Entries are untouched."""
    for entry_type, purpose in STOCK_ENTRY_TYPE_PURPOSES.items():
        if frappe.db.exists("Stock Entry Type", entry_type):
            frappe.db.set_value("Stock Entry Type", entry_type, "purpose", purpose)
    frappe.clear_cache()
