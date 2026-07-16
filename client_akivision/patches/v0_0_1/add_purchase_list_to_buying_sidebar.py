import frappe


def execute():
    sidebar_name = "Buying"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    report_name = "Purchase List"
    report_section = next(
        (
            item
            for item in sidebar.items
            if item.type in ("Section Break", "Card Break") and item.label in ("报表", "Reports")
        ),
        None,
    )
    if not report_section:
        return

    # Remove existing link if present
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'Report'
          AND link_to = %s
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
            "label": report_name,
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
            "child": 1,
            "hidden": 0,
            "is_query_report": 0,
        }
    ).insert(ignore_permissions=True)

    frappe.clear_cache()
