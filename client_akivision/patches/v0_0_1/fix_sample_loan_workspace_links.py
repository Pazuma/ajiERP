import frappe


def execute():
    """Ensure Sample Loan workspace section has correct link_count and visible child links."""
    workspace_name = "Stock"
    if not frappe.db.exists("Workspace", workspace_name):
        return

    workspace = frappe.get_doc("Workspace", workspace_name)

    # Ensure section and links exist
    section = None
    for link in workspace.links:
        if link.type == "Card Break" and link.label == "借出清单":
            section = link
            break

    if not section:
        section = workspace.append(
            "links",
            {
                "type": "Card Break",
                "label": "借出清单",
                "hidden": 0,
                "is_query_report": 0,
                "link_count": 3,
                "onboard": 0,
            },
        )
    else:
        section.link_count = 3

    expected_links = {
        "Sample Loan Out": "Sample Loan Out",
        "Sample Loan Out Return": "Sample Loan Out Return",
        "Finished Goods Status": "Finished Goods Status",
    }

    existing_labels = {link.label for link in workspace.links if link.type == "Link"}
    for label, link_to in expected_links.items():
        if label not in existing_labels:
            workspace.append(
                "links",
                {
                    "type": "Link",
                    "label": label,
                    "link_type": "DocType",
                    "link_to": link_to,
                    "dependencies": "",
                    "hidden": 0,
                    "is_query_report": 0,
                    "link_count": 0,
                    "onboard": 0,
                },
            )

    workspace.save(ignore_permissions=True)
    frappe.clear_cache()
