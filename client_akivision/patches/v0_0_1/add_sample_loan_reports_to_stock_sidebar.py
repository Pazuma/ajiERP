import frappe


REPORTS = (
    ("Sample Loan Out List", "借出样品清单"),
    ("Sample Loan In List", "借回样品清单"),
)


def execute():
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    frappe.reload_doc("client_akivision", "report", "sample_loan_out_list", force=True)
    frappe.reload_doc("client_akivision", "report", "sample_loan_in_list", force=True)

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    report_section = next(
        (
            item
            for item in sidebar.get("items", [])
            if item.type in ("Section Break", "Card Break") and item.label in ("报表", "Reports")
        ),
        None,
    )
    if not report_section:
        return

    report_names = tuple(report_name for report_name, _ in REPORTS)
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'Report' AND link_to IN %s
        """,
        (sidebar_name, report_names),
    )

    insert_idx = report_section.idx + 1
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + %s
        WHERE parent = %s AND idx >= %s
        """,
        (len(REPORTS), sidebar_name, insert_idx),
    )
    for offset, (report_name, label) in enumerate(REPORTS):
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "idx": insert_idx + offset,
                "label": label,
                "type": "Link",
                "link_type": "Report",
                "link_to": report_name,
                "child": 1,
                "is_query_report": 1,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache()
