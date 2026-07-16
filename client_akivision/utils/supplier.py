import frappe
from frappe.utils import cint


@frappe.whitelist()
def get_supplier_list_details(suppliers):
    """Return credit days from the default payment terms template for each supplier."""
    if isinstance(suppliers, str):
        suppliers = frappe.parse_json(suppliers)

    suppliers = [name for name in (suppliers or []) if name]
    if not suppliers:
        return {}

    allowed_suppliers = [
        name
        for name in suppliers
        if frappe.has_permission("Supplier", "read", doc=name)
    ]
    if not allowed_suppliers:
        return {}

    details = {name: {"credit_days": 0} for name in allowed_suppliers}

    supplier_records = frappe.get_all(
        "Supplier",
        filters={"name": ["in", allowed_suppliers]},
        fields=["name", "payment_terms"],
    )

    template_names = {
        s.payment_terms for s in supplier_records if s.payment_terms
    }
    template_credit_days = {}
    if template_names:
        for template in template_names:
            credit_days = frappe.db.get_all(
                "Payment Terms Template Detail",
                filters={"parent": template},
                fields=["credit_days"],
                order_by="idx asc",
                limit=1,
            )
            template_credit_days[template] = cint(credit_days[0].credit_days) if credit_days else 0

    for s in supplier_records:
        details[s.name]["credit_days"] = template_credit_days.get(s.payment_terms, 0)

    return details
