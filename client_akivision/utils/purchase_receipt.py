import frappe


def set_purchase_order_from_items(doc, method=None):
    """Populate the header-level purchase order link from item lines."""
    purchase_orders = {
        item.purchase_order
        for item in doc.items
        if getattr(item, "purchase_order", None)
    }
    if purchase_orders:
        doc.custom_purchase_order = sorted(purchase_orders)[0]
    else:
        doc.custom_purchase_order = None
