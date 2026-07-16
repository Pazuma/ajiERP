import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_columns():
    return [
        {"label": _("Serial No"), "fieldname": "serial_no", "fieldtype": "Link", "options": "Serial No", "width": 130},
        {"label": _("Internal Model"), "fieldname": "internal_model", "fieldtype": "Data", "width": 110},
        {"label": _("External Model"), "fieldname": "external_model", "fieldtype": "Data", "width": 180},
        {"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
        {"label": _("In Date"), "fieldname": "in_date", "fieldtype": "Date", "width": 110},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
        {"label": _("Sub Status"), "fieldname": "sub_status", "fieldtype": "Data", "width": 110},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("Contact Person"), "fieldname": "contact_person", "fieldtype": "Data", "width": 120},
        {"label": _("Phone"), "fieldname": "phone", "fieldtype": "Data", "width": 130},
        {"label": _("Loan / Sales By"), "fieldname": "loan_or_sales_by", "fieldtype": "Data", "width": 120},
        {"label": _("Loan / Sales No"), "fieldname": "loan_or_sales_no", "fieldtype": "Data", "width": 150},
        {"label": _("Loan / Sales Date"), "fieldname": "loan_or_sales_date", "fieldtype": "Date", "width": 130},
        {"label": _("Work Order No"), "fieldname": "work_order_no", "fieldtype": "Data", "width": 130},
        {"label": _("Work Order Status"), "fieldname": "work_order_status", "fieldtype": "Data", "width": 130},
        {"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    rows = frappe.db.sql(
        f"""
        SELECT
            fgs.serial_no,
            fgs.internal_model,
            fgs.external_model,
            fgs.in_qty,
            fgs.in_date,
            fgs.status,
            fgs.sub_status,
            fgs.customer,
            fgs.contact_person,
            fgs.phone,
            fgs.loan_or_sales_by,
            fgs.loan_or_sales_no,
            fgs.loan_or_sales_date,
            fgs.work_order_no,
            fgs.work_order_status,
            fgs.warehouse,
            fgs.remarks
        FROM `tabFinished Goods Status` fgs
        WHERE 1=1 {conditions}
        ORDER BY fgs.in_date DESC, fgs.serial_no DESC
        """,
        filters,
        as_dict=True,
    )

    for row in rows:
        row.in_qty = flt(row.in_qty)

    return rows


def get_report_summary(data):
    total = len(data)
    loan_sample = sum(1 for row in data if row.status == "借出样品")
    sample = sum(1 for row in data if row.status == "样品")
    sale = sum(1 for row in data if row.status == "销售品")
    loaned = sum(1 for row in data if row.sub_status == "已借出")
    sold = sum(1 for row in data if row.sub_status == "已销售")

    return [
        {"value": total, "label": _("Total"), "datatype": "Int", "indicator": "Blue"},
        {"value": loan_sample, "label": _("借出样品"), "datatype": "Int", "indicator": "Blue"},
        {"value": sample, "label": _("样品"), "datatype": "Int", "indicator": "Yellow"},
        {"value": sale, "label": _("销售品"), "datatype": "Int", "indicator": "Green"},
        {"value": loaned, "label": _("已借出"), "datatype": "Int", "indicator": "Blue"},
        {"value": sold, "label": _("已销售"), "datatype": "Int", "indicator": "Green"},
    ]


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append(
            "AND EXISTS (SELECT 1 FROM `tabWarehouse` w WHERE w.name = fgs.warehouse AND w.company = %(company)s)"
        )
    if filters.get("warehouse"):
        conditions.append("AND fgs.warehouse = %(warehouse)s")
    if filters.get("status"):
        conditions.append("AND fgs.status = %(status)s")
    if filters.get("sub_status"):
        conditions.append("AND fgs.sub_status = %(sub_status)s")
    if filters.get("customer"):
        conditions.append("AND fgs.customer = %(customer)s")
    if filters.get("from_date"):
        conditions.append("AND fgs.in_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND fgs.in_date <= %(to_date)s")
    if filters.get("item_code"):
        conditions.append(
            "AND EXISTS (SELECT 1 FROM `tabSerial No` sn WHERE sn.name = fgs.serial_no AND sn.item_code = %(item_code)s)"
        )
    return " ".join(conditions)
