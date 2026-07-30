import frappe


def execute():
    """Add Engineering Drawing Settings below the Manufacturing Tools section."""
    sidebar_name = "Manufacturing"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return
    if frappe.db.exists("Workspace Sidebar Item", {"parent": sidebar_name, "link_type": "DocType", "link_to": "Engineering Drawing Settings"}):
        return
    items = frappe.get_all("Workspace Sidebar Item", filters={"parent": sidebar_name}, fields=["idx", "type", "label"], order_by="idx")
    tools = next((item for item in items if item.type == "Section Break" and item.label in ("Tools", "工具")), None)
    if not tools:
        return
    next_section = next((item for item in items if item.type == "Section Break" and item.idx > tools.idx), None)
    insert_idx = next_section.idx if next_section else len(items) + 1
    frappe.db.sql("UPDATE `tabWorkspace Sidebar Item` SET idx = idx + 1 WHERE parent = %s AND idx >= %s", (sidebar_name, insert_idx))
    frappe.get_doc({
        "doctype": "Workspace Sidebar Item", "parent": sidebar_name, "parenttype": "Workspace Sidebar", "parentfield": "items",
        "idx": insert_idx, "label": "工程图纸设置", "type": "Link", "link_type": "DocType", "link_to": "Engineering Drawing Settings",
        "icon": "settings", "child": 1,
    }).insert(ignore_permissions=True)
    frappe.clear_cache()
