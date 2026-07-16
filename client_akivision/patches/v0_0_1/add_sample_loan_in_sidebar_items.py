import frappe


def execute():
    """Add Sample Loan In links to the Stock Workspace Sidebar under a new section."""
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)

    existing_labels = {item.label for item in sidebar.items}
    if "借回清单" in existing_labels:
        return

    sidebar.append(
        "items",
        {
            "label": "借回清单",
            "type": "Section Break",
            "link_type": "DocType",
        },
    )

    for label, link_to in [
        ("Sample Loan In", "Sample Loan In"),
        ("Sample Loan In Return", "Sample Loan In Return"),
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
