import frappe


def execute():
	"""Keep the GL entry snapshot identifier informational, not a live Link."""
	frappe.reload_doc("china_finance", "doctype", "china_reconciliation_line")

