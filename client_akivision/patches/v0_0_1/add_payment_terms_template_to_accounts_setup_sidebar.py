import frappe


def execute():
    """Add Payment Terms Template under the Accounts Setup sidebar's Setup section."""
    sidebar_name = "Accounts Setup"
    doctype = "Payment Terms Template"

    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    setup_section = next(
        (
            item
            for item in sidebar.items
            if item.type == "Section Break" and item.label in ("设置", "Setup")
        ),
        None,
    )
    if not setup_section:
        return

    if frappe.db.exists(
        "Workspace Sidebar Item",
        {
            "parent": sidebar_name,
            "type": "Link",
            "link_type": "DocType",
            "link_to": doctype,
        },
    ):
        return

    insert_idx = setup_section.idx + 1
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
            "label": "付款条款模板",
            "type": "Link",
            "link_type": "DocType",
            "link_to": doctype,
            "child": 1,
        }
    ).insert(ignore_permissions=True)
    frappe.clear_cache()
