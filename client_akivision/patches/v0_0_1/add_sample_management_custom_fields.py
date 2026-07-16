import frappe


def execute():
    """Install custom fields, warehouses and stock entry types for sample loan management."""
    create_item_custom_fields()
    create_serial_no_custom_fields()
    create_stock_entry_custom_fields()
    create_warehouse_and_stock_entry_types()


def create_item_custom_fields():
    fields = [
        {
            "dt": "Item",
            "fieldname": "custom_internal_model",
            "label": "Internal Model",
            "fieldtype": "Data",
            "insert_after": "item_name",
            "translatable": 0,
        },
        {
            "dt": "Item",
            "fieldname": "custom_external_model",
            "label": "External Model",
            "fieldtype": "Data",
            "insert_after": "custom_internal_model",
            "translatable": 0,
        },
    ]
    create_custom_fields(fields)


def create_serial_no_custom_fields():
    fields = [
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_status",
            "label": "Akivision Status",
            "fieldtype": "Select",
            "options": "\nIn Stock\nOn Loan\nSold\nScrapped\nReturned",
            "insert_after": "status",
            "read_only": 0,
            "translatable": 0,
        },
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_loan_out",
            "label": "Sample Loan Out",
            "fieldtype": "Link",
            "options": "Sample Loan Out",
            "insert_after": "custom_akivision_status",
            "read_only": 1,
            "translatable": 0,
        },
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_customer",
            "label": "Customer",
            "fieldtype": "Link",
            "options": "Customer",
            "insert_after": "custom_akivision_loan_out",
            "read_only": 1,
            "translatable": 0,
        },
        {
            "dt": "Serial No",
            "fieldname": "custom_akivision_sales_order",
            "label": "Sales Order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "insert_after": "custom_akivision_customer",
            "read_only": 1,
            "translatable": 0,
        },
    ]
    create_custom_fields(fields)


def create_stock_entry_custom_fields():
    fields = [
        {
            "dt": "Stock Entry",
            "fieldname": "custom_akivision_sample_loan_doctype",
            "label": "Sample Loan DocType",
            "fieldtype": "Link",
            "options": "DocType",
            "insert_after": "project",
            "read_only": 1,
            "translatable": 0,
        },
        {
            "dt": "Stock Entry",
            "fieldname": "custom_akivision_sample_loan_doc",
            "label": "Sample Loan Document",
            "fieldtype": "Dynamic Link",
            "options": "custom_akivision_sample_loan_doctype",
            "insert_after": "custom_akivision_sample_loan_doctype",
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
    warehouse_name = f"Customer Loan - {abbr}"

    if not frappe.db.exists("Warehouse", warehouse_name):
        root_warehouse = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ""}, "name"
        )
        frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "Customer Loan",
                "company": company,
                "parent_warehouse": root_warehouse,
            }
        ).insert()

    for entry_type, purpose in [
        ("Sample Loan Out", "Material Transfer"),
        ("Sample Loan Out Return", "Material Transfer"),
    ]:
        if not frappe.db.exists("Stock Entry Type", entry_type):
            frappe.get_doc(
                {
                    "doctype": "Stock Entry Type",
                    "name": entry_type,
                    "purpose": purpose,
                }
            ).insert()
