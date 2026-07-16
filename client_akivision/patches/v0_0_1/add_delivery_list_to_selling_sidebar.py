import frappe


def execute():
    """Add Delivery List to the Selling sidebar Reports section without duplicates."""
    sidebar_name = "Selling"
    report_name = "Delivery List"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    section = next(
        (
            item
            for item in sidebar.items
            if item.type == "Section Break" and item.label in ("报表", "Reports")
        ),
        None,
    )
    if not section:
        return

    if frappe.db.exists(
        "Workspace Sidebar Item",
        {"parent": sidebar_name, "type": "Link", "link_type": "Report", "link_to": report_name},
    ):
        return

    insert_idx = section.idx + 1
    frappe.db.sql(
        "UPDATE `tabWorkspace Sidebar Item` SET idx = idx + 1 WHERE parent = %s AND idx >= %s",
        (sidebar_name, insert_idx),
    )
    frappe.get_doc(
        {
            "doctype": "Workspace Sidebar Item",
            "parent": sidebar_name,
            "parenttype": "Workspace Sidebar",
            "parentfield": "items",
            "idx": insert_idx,
            "label": "送货清单",
            "type": "Link",
            "link_type": "Report",
            "link_to": report_name,
            "child": 1,
            "is_query_report": 0,
        }
    ).insert(ignore_permissions=True)
    frappe.clear_cache()
