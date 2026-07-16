import frappe


def execute():
    """Set icon to 'loan' for sample loan sidebar sections."""
    sidebar_name = "Stock"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    for label in ["借出清单", "借回清单"]:
        item_name = frappe.db.get_value(
            "Workspace Sidebar Item",
            {"parent": sidebar_name, "label": label, "type": "Section Break"},
            "name",
        )
        if item_name:
            frappe.db.set_value("Workspace Sidebar Item", item_name, "icon", "loan")

    frappe.clear_cache()
