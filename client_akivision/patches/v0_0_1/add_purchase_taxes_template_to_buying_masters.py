import frappe


def execute():
    """Add Purchase Taxes and Charges Template to the Buying sidebar Masters section."""
    sidebar_name = "Buying"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    masters_section = next(
        (
            item
            for item in sidebar.items
            if item.type in ("Section Break", "Card Break") and item.label == "Masters"
        ),
        None,
    )
    if not masters_section:
        return

    doctype_name = "Purchase Taxes and Charges Template"
    if frappe.db.exists(
        "Workspace Sidebar Item",
        {"parent": sidebar_name, "type": "Link", "link_type": "DocType", "link_to": doctype_name},
    ):
        return

    # Find the first item after the Masters section that belongs to the next section.
    next_section = next(
        (
            item
            for item in sidebar.items
            if item.type in ("Section Break", "Card Break") and item.idx > masters_section.idx
        ),
        None,
    )
    insert_idx = next_section.idx if next_section else len(sidebar.items) + 1

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
            "label": "Purchase Taxes and Charges Template",
            "type": "Link",
            "link_type": "DocType",
            "link_to": doctype_name,
            "child": 1,
            "hidden": 0,
        }
    ).insert(ignore_permissions=True)

    frappe.clear_cache()
