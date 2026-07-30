import frappe


def execute():
    """Hide the Item Price reference column from list views (it carries sync markers)."""
    filters = {"doc_type": "Item Price", "field_name": "reference", "property": "in_list_view"}
    existing = frappe.db.exists("Property Setter", filters)
    if existing:
        frappe.db.set_value("Property Setter", existing, "value", "0", update_modified=False)
        return
    frappe.get_doc(
        {
            "doctype": "Property Setter",
            "doctype_or_field": "DocField",
            **filters,
            "property_type": "Check",
            "value": "0",
        }
    ).insert(ignore_permissions=True)
    frappe.clear_cache(doctype="Item Price")
