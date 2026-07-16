import frappe


ENGLISH_STANDING_NAMES = ["Very Poor", "Poor", "Average", "Excellent"]


def execute():
    """Remove ERPNext's English default standings so Chinese A/B/C/D standings don't overlap."""
    for name in ENGLISH_STANDING_NAMES:
        if frappe.db.exists("Supplier Scorecard Standing", name):
            frappe.delete_doc("Supplier Scorecard Standing", name, ignore_permissions=True)
