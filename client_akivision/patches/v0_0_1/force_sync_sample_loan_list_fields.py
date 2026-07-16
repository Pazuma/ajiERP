import frappe


def execute():
    """Synchronize sample-loan list columns and Chinese field labels."""
    for doctype in ("sample_loan_out", "sample_loan_in"):
        frappe.reload_doc("client_akivision", "doctype", doctype, force=True)
