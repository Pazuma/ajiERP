import frappe


def execute():
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    report_name = "Receipt List"
    old_report_name = "入库清单"
    sidebar_label = "入库清单"
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

    # 清理旧的中文名 Report 记录（如果有的话），避免冲突
    if frappe.db.exists("Report", old_report_name):
        frappe.delete_doc("Report", old_report_name, force=True, ignore_permissions=True)

    # 从 app 文件重载正确的 Receipt List 报表
    frappe.reload_doc("client_akivision", "report", "receipt_list", force=True)

    # 删除旧的中文 sidebar 链接（如果存在）以及新的 Receipt List 链接，避免重复
    for link_to in (old_report_name, report_name):
        frappe.db.sql(
            """
            DELETE FROM `tabWorkspace Sidebar Item`
            WHERE parent = %s AND type = 'Link' AND link_type = 'Report'
              AND link_to = %s
            """,
            (sidebar_name, link_to),
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
            "label": sidebar_label,
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
            "child": 1,
            "hidden": 0,
            "is_query_report": 1,
        }
    ).insert(ignore_permissions=True)

    frappe.clear_cache()
