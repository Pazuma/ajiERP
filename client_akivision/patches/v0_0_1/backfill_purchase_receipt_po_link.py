import frappe


def execute():
    """Backfill custom_purchase_order on existing Purchase Receipts from item lines."""
    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"docstatus": ["<", 2]},
        fields=["name"],
    )

    for pr_name in receipts:
        doc = frappe.get_doc("Purchase Receipt", pr_name.name)
        pos = {item.purchase_order for item in doc.items if item.purchase_order}
        if pos:
            new_value = sorted(pos)[0]
            if doc.custom_purchase_order != new_value:
                frappe.db.set_value(
                    "Purchase Receipt",
                    pr_name.name,
                    "custom_purchase_order",
                    new_value,
                    update_modified=False,
                )
