import frappe


def execute():
    """Add Sample Loan Out / Return / Finished Goods Status links to Stock workspace sidebar."""
    workspace_name = "Stock"
    if not frappe.db.exists("Workspace", workspace_name):
        return

    workspace = frappe.get_doc("Workspace", workspace_name)

    # Check if already added
    existing_labels = {link.label for link in workspace.links}
    if "借出清单" in existing_labels:
        return

    section = {
        "type": "Card Break",
        "label": "借出清单",
        "hidden": 0,
        "is_query_report": 0,
        "link_count": 0,
        "onboard": 0,
    }

    links = [
        {
            "type": "Link",
            "label": "Sample Loan Out",
            "link_type": "DocType",
            "link_to": "Sample Loan Out",
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
        },
        {
            "type": "Link",
            "label": "Sample Loan Out Return",
            "link_type": "DocType",
            "link_to": "Sample Loan Out Return",
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
        },
        {
            "type": "Link",
            "label": "Finished Goods Status",
            "link_type": "DocType",
            "link_to": "Finished Goods Status",
            "dependencies": "",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
        },
    ]

    workspace.append("links", section)
    for link in links:
        workspace.append("links", link)

    workspace.save(ignore_permissions=True)
