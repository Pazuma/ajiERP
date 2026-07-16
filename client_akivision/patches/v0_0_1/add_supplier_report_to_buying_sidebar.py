import frappe


def execute():
    sidebar_name = "Buying"
    report_name = "Supplier Performance Evaluation"

    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    report_section = next(
        (
            item
            for item in sidebar.items
            if item.type in ("Section Break", "Card Break")
            and item.label in ("报表", "Reports")
        ),
        None,
    )
    if not report_section:
        return

    existing = frappe.db.exists(
        "Workspace Sidebar Item",
        {
            "parent": sidebar_name,
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
        },
    )
    if existing:
        return

    insert_idx = report_section.idx + 1
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + 1
        WHERE parent = %s AND idx >= %s
        """,
        (sidebar_name, insert_idx),
    )

    frappe.get_doc(
        {
            "doctype": "Workspace Sidebar Item",
            "parent": sidebar_name,
            "parenttype": "Workspace Sidebar",
            "parentfield": "items",
            "idx": insert_idx,
            "label": report_name,
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
            "child": 1,
            "hidden": 0,
            "is_query_report": 1,
        }
    ).insert(ignore_permissions=True)

    frappe.clear_cache()
