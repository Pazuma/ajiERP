import frappe

from client_akivision.utils import quote_pricing


def execute():
    """Backfill tier Pricing Rules and Item Prices for Supplier Quotations submitted
    before the sync hook existed.

    Replays oldest-first so the newest quotation wins each price point. Idempotent:
    the sync upserts by (supplier, item, min_qty / price_list / uom).
    """
    names = frappe.get_all(
        "Supplier Quotation",
        filters={"docstatus": 1},
        pluck="name",
        order_by="transaction_date, creation",
    )
    for index, name in enumerate(names, start=1):
        doc = frappe.get_doc("Supplier Quotation", name)
        quote_pricing.sync_quotation_tiers(doc)
        if index % 50 == 0:
            frappe.logger("client_akivision").info(
                f"Backfilled quote prices for {index}/{len(names)} quotations"
            )
