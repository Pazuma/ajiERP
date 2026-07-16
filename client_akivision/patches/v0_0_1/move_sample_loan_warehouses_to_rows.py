import frappe


def execute():
    """Backfill per-row warehouse fields from parent header before header fields are removed.

    This patch runs before model sync so the legacy parent warehouse columns still exist.
    Any child rows that do not yet have a warehouse value are populated from the parent
    header, ensuring existing documents remain valid after the header fields are removed.
    """
    backfill_sample_loan_out()
    backfill_sample_loan_out_return()
    backfill_sample_loan_in()
    backfill_sample_loan_in_return()


def _columns_exist(doctype, columns):
    """Return True if all given columns exist in the doctype's table."""
    try:
        table = f"tab{doctype.replace(' ', '_')}"
        existing = {row[0] for row in frappe.db.sql(f"SHOW COLUMNS FROM `{table}`", as_list=True)}
        return all(col in existing for col in columns)
    except Exception:
        return False


def backfill_sample_loan_out():
    if not _columns_exist("Sample Loan Out", ["source_warehouse", "loan_warehouse"]):
        return

    for doc in frappe.get_all(
        "Sample Loan Out",
        fields=["name", "source_warehouse", "loan_warehouse"],
    ):
        frappe.db.sql(
            """
            UPDATE `tabSample Loan Out Item`
            SET source_warehouse = COALESCE(NULLIF(source_warehouse, ''), %s),
                loan_warehouse = COALESCE(NULLIF(loan_warehouse, ''), %s)
            WHERE parent = %s AND parenttype = 'Sample Loan Out'
            """,
            (doc.source_warehouse, doc.loan_warehouse, doc.name),
        )


def backfill_sample_loan_out_return():
    if not _columns_exist("Sample Loan Out Return", ["sample_loan_out"]):
        return

    for doc in frappe.get_all("Sample Loan Out Return", fields=["name", "sample_loan_out"]):
        loan_out = frappe.db.get_value(
            "Sample Loan Out",
            doc.sample_loan_out,
            ["source_warehouse", "loan_warehouse"],
            as_dict=1,
        )
        if not loan_out:
            continue

        for row in frappe.get_all(
            "Sample Loan Out Return Item",
            filters={"parent": doc.name, "parenttype": "Sample Loan Out Return"},
            fields=["name", "serial_no"],
        ):
            source_wh = loan_out.source_warehouse
            loan_wh = loan_out.loan_warehouse

            parent_row = frappe.db.get_value(
                "Sample Loan Out Item",
                {
                    "parent": doc.sample_loan_out,
                    "parenttype": "Sample Loan Out",
                    "serial_no": row.serial_no,
                },
                ["source_warehouse", "loan_warehouse"],
                as_dict=1,
            )
            if parent_row:
                source_wh = parent_row.source_warehouse or source_wh
                loan_wh = parent_row.loan_warehouse or loan_wh

            frappe.db.set_value(
                "Sample Loan Out Return Item",
                row.name,
                {
                    "source_warehouse": source_wh,
                    "loan_warehouse": loan_wh,
                },
            )


def backfill_sample_loan_in():
    if not _columns_exist("Sample Loan In", ["loan_warehouse"]):
        return

    for doc in frappe.get_all("Sample Loan In", fields=["name", "loan_warehouse"]):
        frappe.db.sql(
            """
            UPDATE `tabSample Loan In Item`
            SET loan_warehouse = COALESCE(NULLIF(loan_warehouse, ''), %s)
            WHERE parent = %s AND parenttype = 'Sample Loan In'
            """,
            (doc.loan_warehouse, doc.name),
        )


def backfill_sample_loan_in_return():
    if not _columns_exist("Sample Loan In Return", ["sample_loan_in"]):
        return

    for doc in frappe.get_all("Sample Loan In Return", fields=["name", "sample_loan_in"]):
        loan_in = frappe.db.get_value(
            "Sample Loan In",
            doc.sample_loan_in,
            ["loan_warehouse"],
            as_dict=1,
        )
        if not loan_in:
            continue

        for row in frappe.get_all(
            "Sample Loan In Return Item",
            filters={"parent": doc.name, "parenttype": "Sample Loan In Return"},
            fields=["name", "loan_in_item"],
        ):
            loan_wh = loan_in.loan_warehouse

            parent_row = frappe.db.get_value(
                "Sample Loan In Item",
                row.loan_in_item,
                "loan_warehouse",
            )
            if parent_row:
                loan_wh = parent_row or loan_wh

            frappe.db.set_value(
                "Sample Loan In Return Item",
                row.name,
                {"loan_warehouse": loan_wh},
            )
