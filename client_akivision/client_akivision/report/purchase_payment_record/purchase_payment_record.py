import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_columns():
    return [
        {"label": _("付款日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
        {"label": _("采购单号"), "fieldname": "purchase_order", "fieldtype": "Data", "width": 160},
        {"label": _("供应商名称"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
        {"label": _("付款金额"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
        {"label": _("付款类型"), "fieldname": "payment_category", "fieldtype": "Data", "width": 110},
        {"label": _("对账归属月份"), "fieldname": "reconciliation_month", "fieldtype": "Data", "width": 120},
        {"label": _("付款年份"), "fieldname": "payment_year", "fieldtype": "Int", "width": 100},
        {"label": _("付款月份"), "fieldname": "payment_month", "fieldtype": "Int", "width": 100},
    ]


def get_data(filters):
    conditions = ["pe.docstatus = 1", "pe.payment_type = 'Pay'"]
    if filters.get("company"):
        conditions.append("pe.company = %(company)s")
    if filters.get("supplier"):
        conditions.append("pe.party = %(supplier)s")
    if filters.get("from_date"):
        conditions.append("pe.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("pe.posting_date <= %(to_date)s")
    rows = frappe.db.sql(
        f"""
        SELECT pe.posting_date, pe.party AS supplier, pe.mode_of_payment,
            per.reference_doctype, COALESCE(per.allocated_amount, pe.paid_amount) AS paid_amount,
            GROUP_CONCAT(
                DISTINCT CASE WHEN per.reference_doctype = 'Purchase Order' THEN per.reference_name ELSE pii.purchase_order END
                ORDER BY CASE WHEN per.reference_doctype = 'Purchase Order' THEN per.reference_name ELSE pii.purchase_order END
                SEPARATOR ', '
            ) AS purchase_order
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        LEFT JOIN `tabPurchase Invoice Item` pii
            ON per.reference_doctype = 'Purchase Invoice' AND pii.parent = per.reference_name
        WHERE {' AND '.join(conditions)}
        GROUP BY pe.name, per.name
        ORDER BY pe.posting_date DESC, pe.name DESC
        """,
        filters,
        as_dict=True,
    )
    for row in rows:
        row.payment_category = payment_category(row.reference_doctype, row.mode_of_payment)
        row.reconciliation_month = row.posting_date.strftime("%Y-%m")
        row.payment_year = row.posting_date.year
        row.payment_month = row.posting_date.month
    return rows


def payment_category(reference_doctype, mode_of_payment):
    if reference_doctype in ("Purchase Invoice", "Purchase Order"):
        return _("货款")
    if reference_doctype == "Expense Claim":
        return _("费用报销")
    return mode_of_payment or _("其他付款")


def get_report_summary(data):
    return [
        {"label": _("付款笔数"), "value": len(data), "datatype": "Int"},
        {
            "label": _("本次付款金额"),
            "value": sum(flt(row.paid_amount) for row in data),
            "datatype": "Currency",
            "indicator": "orange",
        },
    ]
