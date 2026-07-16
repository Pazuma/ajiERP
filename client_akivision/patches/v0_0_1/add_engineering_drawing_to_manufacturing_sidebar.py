import frappe


def execute():
    sidebar_name = "Manufacturing"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return
    if frappe.db.exists(
        "Workspace Sidebar Item",
        {"parent": sidebar_name, "type": "Link", "link_type": "DocType", "link_to": "Engineering Drawing"},
    ):
        return

    items = frappe.get_all(
        "Workspace Sidebar Item", filters={"parent": sidebar_name}, fields=["idx", "type", "link_to"], order_by="idx"
    )
    bom_item = next((item for item in items if item.type == "Link" and item.link_to == "BOM"), None)
    insert_idx = (bom_item.idx + 1) if bom_item else len(items) + 1
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
            "label": "工程图纸",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Engineering Drawing",
            "icon": "file",
            "child": 0,
        }
    ).insert(ignore_permissions=True)
    frappe.clear_cache()
