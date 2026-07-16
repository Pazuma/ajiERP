import frappe


PAYMENT_ENTRY_LINKS = (
    ("收款", "Receive"),
    ("付款", "Pay"),
)


def execute():
    """Replace the generic Payment Entry list link with Receive and Pay list links."""
    sidebar_name = "Payments"
    if not frappe.db.exists("Workspace Sidebar", sidebar_name):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_name)
    payment_section = next(
        (
            item
            for item in sidebar.get("items", [])
            if item.type == "Section Break" and item.label in ("Payments", "付款")
        ),
        None,
    )
    if not payment_section:
        return

    # Removing all existing Payment Entry sidebar links makes this patch idempotent
    # and prevents the generic unfiltered entry from remaining alongside the two lists.
    frappe.db.sql(
        """
        DELETE FROM `tabWorkspace Sidebar Item`
        WHERE parent = %s AND type = 'Link' AND link_type = 'DocType' AND link_to = 'Payment Entry'
        """,
        (sidebar_name,),
    )

    insert_idx = payment_section.idx + 1
    frappe.db.sql(
        """
        UPDATE `tabWorkspace Sidebar Item`
        SET idx = idx + %s
        WHERE parent = %s AND idx >= %s
        """,
        (len(PAYMENT_ENTRY_LINKS), sidebar_name, insert_idx),
    )

    for offset, (label, payment_type) in enumerate(PAYMENT_ENTRY_LINKS):
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar Item",
                "parent": sidebar_name,
                "parenttype": "Workspace Sidebar",
                "parentfield": "items",
                "idx": insert_idx + offset,
                "label": label,
                "type": "Link",
                "link_type": "DocType",
                "link_to": "Payment Entry",
                "route_options": frappe.as_json({"payment_type": payment_type}),
                "child": 1,
            }
        ).insert(ignore_permissions=True)

    frappe.clear_cache()
