import frappe


def execute():
    """Add Purchase Delay Analysis report under Buying workspace sidebar Reports section."""
    sidebar_name = "Buying"
    report_name = "Purchase Delay Analysis"
    label = "采购到货延迟分析"

    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    # Reload report from app
    frappe.reload_doc("client_akivision", "report", "purchase_delay_analysis", force=True)

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

    # Remove existing link to avoid duplicates
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'Report' AND link_to = %s
        """,
        (sidebar_name, report_name),
    )

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
            "label": label,
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
            "child": 1,
            "hidden": 0,
            "is_query_report": 1,
        }
    ).insert(ignore_permissions=True)

    frappe.clear_cache()
