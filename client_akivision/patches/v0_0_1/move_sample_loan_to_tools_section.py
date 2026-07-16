import frappe


def execute():
    """Move Sample Loan sidebar links under Stock workspace's native Tools section."""
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    link_targets = [
        "Sample Loan Out",
        "Sample Loan Out Return",
        "Finished Goods Status",
        "Sample Loan In",
        "Sample Loan In Return",
    ]

    # Remove old standalone section breaks and their children
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND label IN ('借出清单', '借回清单')
        """,
        (sidebar_name,),
    )

    # Remove any existing sample loan links that may be elsewhere
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s
          AND type = 'Link'
          AND link_to IN %s
        """,
        (sidebar_name, tuple(link_targets)),
    )

    # Find the Setup section break; insert our links right before it so they belong to Tools
    setup_item = frappe.db.get_value(
        "Workspace Sidebar Item",
        {"parent": sidebar_name, "label": "Setup", "type": "Section Break"},
        ["name", "idx"],
        as_dict=1,
    )
    if not setup_item:
        return

    insert_idx = setup_item.idx
    shift = len(link_targets)

    # Shift Setup and everything after it to make room
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + %s
        WHERE parent = %s AND idx >= %s
        """,
        (shift, sidebar_name, insert_idx),
    )

    # Insert links as children of the preceding Tools section
    for offset, link_to in enumerate(link_targets):
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "idx": insert_idx + offset,
                "label": link_to,
                "type": "Link",
                "link_type": "DocType",
                "link_to": link_to,
                "child": 1,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache()
