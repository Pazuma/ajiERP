import frappe

from client_akivision.utils import quote_pricing


def execute():
    """Backfill tier Pricing Rules for Supplier Quote Imports generated before tier sync existed.

    Idempotent: quote_pricing.sync_pricing_rules upserts by (supplier, item, min_qty),
    so replaying never duplicates rules.
    """
    for name in frappe.get_all("Supplier Quote Import", filters={"status": "Generated"}, pluck="name"):
        doc = frappe.get_doc("Supplier Quote Import", name)
        quote_pricing.sync_pricing_rules(doc)
