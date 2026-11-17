"""Append navigation after existing sidebar filters without changing old entries."""
import frappe


def configure_entries(bootinfo):
    if not frappe.db.exists("DocType", "Product Cost Quotation") or not frappe.has_permission("Product Cost Quotation", "read"):
        return
    sidebars = bootinfo.get("workspace_sidebar_item", {})
    for key in ("selling", "manufacturing"):
        sidebar = sidebars.get(key)
        if sidebar:
            sidebar["items"] = [i for i in sidebar.setdefault("items", []) if i.get("link_to") != "Product Cost Quotation"]
    sidebar = sidebars.get("基础资料")
    if not sidebar:
        return
    items = sidebar.setdefault("items", [])
    if any(i.get("link_to") == "Product Cost Quotation" for i in items):
        return
    position = next((idx + 1 for idx, item in enumerate(items)
                     if item.get("link_to") == "Item" or "/app/item" in str(item.get("link_to") or "")), len(items))
    items.insert(position, frappe._dict(type="Link", label="产品成本报价单", link_to="Product Cost Quotation", link_type="DocType", icon="money-coins", child=1))
