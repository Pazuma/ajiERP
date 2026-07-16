import frappe


def execute():
    """Allow editing remarks after submit on Stock Entry and Purchase Receipt."""
    for doctype in ("Stock Entry", "Purchase Receipt"):
        if not frappe.db.exists(
            "Property Setter",
            {"doc_type": doctype, "field_name": "remarks", "property": "allow_on_submit"},
        ):
            frappe.get_doc(
                {
                    "doctype": "Property Setter",
                    "doctype_or_field": "DocField",
                    "doc_type": doctype,
                    "field_name": "remarks",
                    "property": "allow_on_submit",
                    "property_type": "Check",
                    "value": "1",
                }
            ).insert()
        else:
            frappe.db.set_value(
                "Property Setter",
                {"doc_type": doctype, "field_name": "remarks", "property": "allow_on_submit"},
                "value",
                "1",
            )

    frappe.clear_cache()
