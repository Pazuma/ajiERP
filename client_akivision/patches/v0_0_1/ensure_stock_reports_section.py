import frappe


def execute():
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)

    # 先从 app 文件重载两个报表，确保 Report 记录存在
    for report_folder in ("receipt_list", "outbound_list"):
        frappe.reload_doc("client_akivision", "report", report_folder, force=True)

    # 查找或创建 Reports 分节符
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
        max_idx = max((item.idx for item in sidebar.items), default=0)
        section_idx = max_idx + 1
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "idx": section_idx,
                "label": "Reports",
                "type": "Section Break",
                "collapsible": 1,
                "child": 0,
                "indent": 1,
                "keep_closed": 1,
            }
        ).insert(ignore_permissions=True)
        insert_idx = section_idx + 1
    else:
        insert_idx = report_section.idx + 1

    report_names = {
        "Receipt List": "入库清单",
        "Outbound List": "出库清单",
    }

    # 删除已有的链接，避免重复
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'Report'
          AND link_to IN %s
        """,
        (sidebar_name, tuple(report_names.keys())),
    )

    # 腾出位置
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + %s
        WHERE parent = %s AND idx >= %s
        """,
        (len(report_names), sidebar_name, insert_idx),
    )

    for offset, (report_name, label) in enumerate(report_names.items()):
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
                "hidden": 0,
                "is_query_report": 1,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache()
