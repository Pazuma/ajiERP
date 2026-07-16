import frappe


def execute():
    """Fix Sample Loan Out status for submitted documents.

    The status field is read-only and setting it as an attribute during
    on_submit did not persist for some documents, leaving them as 'Draft'.
    This patch recomputes the correct status from the child items.
    """
    for doc in frappe.get_all(
        "Sample Loan Out",
        filters={"docstatus": 1},
        fields=["name", "status", "sales_order_reference"],
    ):
        items = frappe.get_all(
            "Sample Loan Out Item",
            filters={"parent": doc.name, "parenttype": "Sample Loan Out"},
            fields=["returned", "disposition"],
        )
        if not items:
            continue

        total = len(items)
        returned = sum(1 for row in items if row.returned)
        sold = sum(1 for row in items if row.disposition == "Sold")

        if doc.sales_order_reference or (sold > 0 and (sold + returned) >= total):
            status = "Converted to Sales"
        elif returned == total:
            status = "Returned"
        elif returned > 0:
            status = "Partially Returned"
        else:
            status = "Loaned"

        if doc.status != status:
            frappe.db.set_value("Sample Loan Out", doc.name, "status", status)
