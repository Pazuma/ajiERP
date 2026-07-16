import frappe


def execute():
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    report_names = ["汇总计算", "Realtime Inventory"]
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

    insert_idx = report_section.idx + 1
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'Report'
          AND link_to IN %s
        """,
        (sidebar_name, tuple(report_names)),
    )
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + %s
        WHERE parent = %s AND idx >= %s
        """,
        (len(report_names), sidebar_name, insert_idx),
    )

    for offset, report_name in enumerate(report_names):
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "idx": insert_idx + offset,
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
