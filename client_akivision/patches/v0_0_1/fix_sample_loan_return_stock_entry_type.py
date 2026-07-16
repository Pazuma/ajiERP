import frappe


def execute():
    """Rename the erroneous Stock Entry Type 'Sample Loan Return' to 'Sample Loan Out Return'.

    The correct type used by Sample Loan Out Return documents is 'Sample Loan Out Return'.
    If an old 'Sample Loan Return' record exists (from an earlier manual/config mistake),
    this patch moves all linked Stock Entries to the correct type and removes the old one.
    """
    old_type = "Sample Loan Return"
    correct_type = "Sample Loan Out Return"

    # Ensure the correct type exists with the right purpose.
    if not frappe.db.exists("Stock Entry Type", correct_type):
        frappe.get_doc(
            {
                "doctype": "Stock Entry Type",
                "name": correct_type,
                "purpose": "Material Transfer",
            }
        ).insert()

    # Nothing to clean up if the wrong type was never created.
    if not frappe.db.exists("Stock Entry Type", old_type):
        return

    # Move all Stock Entries that still reference the wrong type.
    frappe.db.sql(
        """
        update `tabStock Entry`
        set stock_entry_type = %s
        where stock_entry_type = %s
        """,
        (correct_type, old_type),
    )

    # Remove the erroneous Stock Entry Type record.
    frappe.delete_doc("Stock Entry Type", old_type, force=1)
