import frappe


def execute():
    """Install custom fields, warehouse and stock entry types for sample loan in management."""
    create_serial_no_custom_fields()
    create_warehouse_and_stock_entry_types()


def create_serial_no_custom_fields():
    fields = [
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_loan_in",
            "label": "Sample Loan In",
            "fieldtype": "Link",
            "options": "Sample Loan In",
            "insert_after": "custom_akivision_sales_order",
            "read_only": 1,
            "translatable": 0,
        },
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_supplier",
            "label": "Supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "insert_after": "custom_akivision_loan_in",
            "read_only": 1,
            "translatable": 0,
        },
    ]
    create_custom_fields(fields)


def create_custom_fields(fields):
    for field in fields:
        if frappe.db.exists("Custom Field", {"dt": field["dt"], "fieldname": field["fieldname"]}):
            continue
        frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": field["dt"],
                "fieldname": field["fieldname"],
                "label": field["label"],
                "fieldtype": field["fieldtype"],
                "options": field.get("options"),
                "insert_after": field.get("insert_after"),
                "read_only": field.get("read_only", 0),
                "translatable": field.get("translatable", 0),
            }
        ).insert()


def create_warehouse_and_stock_entry_types():
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_value(
        "Company", {"is_group": 0}, "name"
    )
    if not company:
        return

    abbr = frappe.db.get_value("Company", company, "abbr")
    warehouse_name = f"Supplier Loan - {abbr}"

    if not frappe.db.exists("Warehouse", warehouse_name):
        root_warehouse = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ""}, "name"
        )
        frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "Supplier Loan",
                "company": company,
                "parent_warehouse": root_warehouse,
            }
        ).insert()

    for entry_type, purpose in [
        ("Sample Loan In", "Material Receipt"),
        ("Sample Loan In Return", "Material Issue"),
    ]:
        if not frappe.db.exists("Stock Entry Type", entry_type):
            frappe.get_doc(
                {
                    "doctype": "Stock Entry Type",
                    "name": entry_type,
                    "purpose": purpose,
                }
            ).insert()
