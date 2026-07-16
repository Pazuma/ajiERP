import frappe

from client_akivision.utils.sample_loan import update_parent_return_status


def execute():
    """Ensure items converted to sales are not counted as returned.

    Previously, create_sales_order_from_loan set returned=1 on sold rows,
    which incorrectly increased the returned quantity. This patch clears the
    returned flag for sold items and recomputes each parent loan status.
    """
    frappe.db.sql(
        """
        UPDATE `tabSample Loan Out Item`
        SET returned = 0, return_date = NULL
        WHERE parenttype = 'Sample Loan Out' AND disposition = 'Sold'
        """
    )

    for name in frappe.get_all("Sample Loan Out", pluck="name"):
        update_parent_return_status(name)
