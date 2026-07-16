import frappe


ITEMS = (
    ("Report", "Receipt Record", "回款记录"),
    ("Report", "Purchase Payment Record", "付款记录"),
    ("DocType", "Payment Entry", "Payment Entry"),
)


def execute():
    sidebar_name = "Payments"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return
    frappe.reload_doc("client_akivision", "report", "receipt_record", force=True)
    frappe.reload_doc("client_akivision", "report", "purchase_payment_record", force=True)
    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    section = next((item for item in sidebar.get("items", []) if item.type == "Section Break" and item.label in ("Payments", "付款")), None)
    if not section:
        return
    frappe.db.sql("""DELETE FROM `tabWorkspace Sidebar Item` WHERE parent = %s AND type = 'Link' AND ((link_type = 'DocType' AND link_to = 'Payment Entry') OR (link_type = 'Report' AND link_to IN %s))""", (sidebar_name, ("Receipt Record", "Purchase Payment Record")))
    insert_idx = section.idx + 1
    frappe.db.sql("UPDATE `tabWorkspace Sidebar Item` SET idx = idx + %s WHERE parent = %s AND idx >= %s", (len(ITEMS), sidebar_name, insert_idx))
    for offset, (link_type, name, label) in enumerate(ITEMS):
        item = {"doctype": "Workspace Sidebar Item", "parent": sidebar_name, "parenttype": "Workspace Sidebar", "parentfield": "items", "idx": insert_idx + offset, "label": label, "type": "Link", "link_type": link_type, "link_to": name, "child": 1}
        if link_type == "Report":
            item["is_query_report"] = 1
        frappe.get_doc(item).insert(ignore_permissions=True)
    frappe.clear_cache()
