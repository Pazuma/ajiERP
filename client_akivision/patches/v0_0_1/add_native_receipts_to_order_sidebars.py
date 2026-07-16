import frappe


def execute():
    add_after_order(
        sidebar_name="Buying",
        order_doctype="Purchase Order",
        target_doctype="Purchase Receipt",
        label="Purchase Receipt",
        icon="receipt-text",
    )
    add_after_order(
        sidebar_name="Selling",
        order_doctype="Sales Order",
        target_doctype="Delivery Note",
        label="Delivery Note",
        icon="truck",
    )
    frappe.clear_cache()


def add_after_order(sidebar_name, order_doctype, target_doctype, label, icon):
    """Place a native stock transaction immediately after its order link."""
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    items = frappe.get_all(
        "Workspace Sidebar Item",
        filters={"parent": sidebar_name},
        fields=["name", "link_to", "link_type"],
        order_by="idx, creation",
    )
    anchor_index = next(
        (
            index
            for index, item in enumerate(items)
            if item.link_type == "DocType" and item.link_to == order_doctype
        ),
        None,
    )
    if anchor_index is None:
        return

    targets = [
        item
        for item in items
        if item.link_type == "DocType" and item.link_to == target_doctype
    ]
    target = targets[0] if targets else None
    duplicate_names = {duplicate.name for duplicate in targets[1:]}
    for duplicate in targets[1:]:
        frappe.db.delete("Workspace Sidebar Item", {"name": duplicate.name})
    items = [item for item in items if item.name not in duplicate_names]

    if not target:
        target = frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "type": "Link",
                "link_type": "DocType",
                "link_to": target_doctype,
            }
        )
        target.insert(ignore_permissions=True)
        items.append(frappe._dict({"name": target.name, "link_to": target_doctype, "link_type": "DocType"}))

    items = [item for item in items if item.name != target.name]
    anchor_index = next(index for index, item in enumerate(items) if item.link_to == order_doctype)
    items.insert(anchor_index + 1, frappe._dict({"name": target.name, "link_to": target_doctype}))

    frappe.db.set_value(
        "Workspace Sidebar Item",
        target.name,
        {
            "label": label,
            "icon": icon,
            "child": 0,
            "collapsible": 1,
            "indent": 0,
            "keep_closed": 0,
            "show_arrow": 0,
        },
    )
    for index, item in enumerate(items, start=1):
        frappe.db.set_value("Workspace Sidebar Item", item.name, "idx", index)
