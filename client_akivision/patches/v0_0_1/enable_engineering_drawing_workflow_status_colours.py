import frappe


def execute():
    """Allow the workflow state style to control Engineering Drawing status pills."""
    workflow_name = frappe.db.get_value(
        "Workflow", {"document_type": "Engineering Drawing", "is_active": 1}, "name"
    )
    if not workflow_name:
        return

    frappe.db.set_value(
        "Workflow Document State",
        {"parent": workflow_name, "state": "Finalized"},
        "avoid_status_override",
        0,
        update_modified=False,
    )
    frappe.clear_cache(doctype="Engineering Drawing")
