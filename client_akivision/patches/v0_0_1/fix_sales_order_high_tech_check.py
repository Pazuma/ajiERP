import frappe


def execute():
    """Fix existing high-tech revenue field to be a Check field editable after submit."""
    field_name = frappe.db.get_value(
        "Custom Field", {"dt": "Sales Order", "fieldname": "custom_is_high_tech_revenue"}
    )
    if not field_name:
        return

    # Update the Custom Field definition first so updatedb sees a Check field.
    frappe.db.set_value(
        "Custom Field",
        field_name,
        {
            "fieldtype": "Check",
            "options": "",
            "default": "0",
            "allow_on_submit": 1,
            "no_copy": 0,
        },
    )

    # Convert legacy Select values (是/否) to boolean values before changing the column type.
    frappe.db.sql(
        """
        UPDATE `tabSales Order`
        SET custom_is_high_tech_revenue = CASE
            WHEN custom_is_high_tech_revenue = '是' THEN '1'
            WHEN custom_is_high_tech_revenue = '否' THEN '0'
            ELSE custom_is_high_tech_revenue
        END
        """
    )

    # Sync the DocType schema so the column becomes tinyint for a Check field.
    frappe.db.updatedb("Sales Order")

    # Ensure the DocField record also allows editing after submit.
    frappe.db.sql(
        """
        UPDATE `tabDocField`
        SET fieldtype = 'Check', options = '', `default` = '0', allow_on_submit = 1, no_copy = 0
        WHERE parent = 'Sales Order' AND fieldname = 'custom_is_high_tech_revenue'
        """
    )

    frappe.clear_cache()
