import frappe


def execute():
    """Add Sample Loan links to the Stock Workspace Sidebar as child items under a new section."""
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)

    # Check if already added
    existing_labels = {item.label for item in sidebar.items}
    if "借出清单" in existing_labels:
        return

    # Append the section and child links at the end
    sidebar.append(
        "items",
        {
            "label": "借出清单",
            "type": "Section Break",
            "link_type": "DocType",
        },
    )

    for label, link_to in [
        ("Sample Loan Out", "Sample Loan Out"),
        ("Sample Loan Out Return", "Sample Loan Out Return"),
        ("Finished Goods Status", "Finished Goods Status"),
    ]:
        sidebar.append(
            "items",
            {
                "label": label,
                "type": "Link",
                "link_type": "DocType",
                "link_to": link_to,
                "child": 1,
            },
        )

    sidebar.save(ignore_permissions=True)
    frappe.clear_cache()
