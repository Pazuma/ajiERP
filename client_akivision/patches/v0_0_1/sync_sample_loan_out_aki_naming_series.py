import frappe


OLD_SERIES = "SLO-.YY.-.#####"
DEFAULT_SERIES = "AKI.YYYY.MM.DD.-.##"


def execute():
    """Replace the legacy Sample Loan Out series while preserving user custom series."""
    frappe.reload_doc("client_akivision", "doctype", "sample_loan_out", force=True)

    property_setter = frappe.db.get_value(
        "Property Setter",
        {
            "doc_type": "Sample Loan Out",
            "field_name": "naming_series",
            "property": "options",
        },
        ["name", "value"],
        as_dict=True,
    )
    if property_setter and property_setter.value == OLD_SERIES:
        frappe.db.set_value("Property Setter", property_setter.name, "value", DEFAULT_SERIES)

    frappe.clear_cache(doctype="Sample Loan Out")
