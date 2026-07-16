import frappe


@frappe.whitelist()
def get_customer_list_details(customers):
    """Return the first sales person for each customer."""
    if isinstance(customers, str):
        customers = frappe.parse_json(customers)

    customers = [name for name in (customers or []) if name]
    if not customers:
        return {}

    allowed_customers = [
        name
        for name in customers
        if frappe.has_permission("Customer", "read", doc=name)
    ]
    if not allowed_customers:
        return {}

    details = {name: {"sales_person": ""} for name in allowed_customers}

    seen = set()
    sales_team_rows = frappe.get_all(
        "Sales Team",
        filters={"parenttype": "Customer", "parent": ["in", allowed_customers]},
        fields=["parent", "sales_person"],
        order_by="parent asc, idx asc",
    )

    for row in sales_team_rows:
        if row.parent in seen:
            continue
        details[row.parent]["sales_person"] = row.sales_person or ""
        seen.add(row.parent)

    return details
