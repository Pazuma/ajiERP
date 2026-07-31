import frappe

from custom_filters import quote_pricing


def execute():
	"""Backfill submitted supplier quotations into the shared price engine."""
	names = frappe.get_all(
		"Supplier Quotation",
		filters={"docstatus": 1},
		pluck="name",
		order_by="transaction_date, creation",
	)
	for name in names:
		quote_pricing.sync_quotation_tiers(frappe.get_doc("Supplier Quotation", name))
