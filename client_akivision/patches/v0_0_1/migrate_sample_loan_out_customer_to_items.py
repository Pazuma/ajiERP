import frappe


def execute():
    """Move legacy Sample Loan Out customer metadata from headers to item rows."""
    frappe.reload_doc("client_akivision", "doctype", "sample_loan_out", force=True)
    frappe.reload_doc("client_akivision", "doctype", "sample_loan_out_item", force=True)

    frappe.db.sql(
        """
        UPDATE `tabSample Loan Out Item` item
        INNER JOIN `tabSample Loan Out` loan ON loan.name = item.parent
        SET
            item.customer = COALESCE(NULLIF(item.customer, ''), loan.customer),
            item.contact_person = COALESCE(NULLIF(item.contact_person, ''), loan.contact_person),
            item.phone = COALESCE(NULLIF(item.phone, ''), loan.phone),
            item.loaned_by = COALESCE(NULLIF(item.loaned_by, ''), loan.loaned_by),
            item.loan_form = COALESCE(NULLIF(item.loan_form, ''), loan.loan_form),
            item.qty = COALESCE(item.qty, 1),
            item.status = COALESCE(
                NULLIF(item.status, ''),
                CASE
                    WHEN item.disposition = 'Sold' THEN '已转销售'
                    WHEN item.disposition = 'Scrapped' THEN '已报废'
                    WHEN item.returned = 1 THEN '已归还'
                    ELSE '借出中'
                END
            )
        WHERE item.parenttype = 'Sample Loan Out'
        """
    )
    frappe.clear_cache(doctype="Sample Loan Out")
