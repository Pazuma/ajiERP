import frappe


def execute():
    """Apply contract-number naming to new Sample Loan Out documents."""
    frappe.reload_doc("client_akivision", "doctype", "sample_loan_out", force=True)
