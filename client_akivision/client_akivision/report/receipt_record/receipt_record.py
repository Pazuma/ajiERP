import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_columns():
    return [
        {"label": _("年份"), "fieldname": "year", "fieldtype": "Int", "width": 70},
        {"label": _("月份"), "fieldname": "month", "fieldtype": "Int", "width": 60},
        {"label": _("送货日期"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
        {"label": _("客户名称"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
        {"label": _("客户代码"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
        {"label": _("订单号"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 140},
        {"label": _("送货单号"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 140},
        {"label": _("内部机号"), "fieldname": "internal_model", "fieldtype": "Data", "width": 110},
        {"label": _("型号"), "fieldname": "external_model", "fieldtype": "Data", "width": 140},
        {"label": _("总金额"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 110},
        {"label": _("已收金额"), "fieldname": "received_amount", "fieldtype": "Currency", "width": 110},
        {"label": _("未收金额"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 110},
        {"label": _("约定收款日期"), "fieldname": "due_date", "fieldtype": "Date", "width": 110},
        {"label": _("应收账天数"), "fieldname": "receivable_days", "fieldtype": "Int", "width": 105},
        {"label": _("账期区间"), "fieldname": "credit_period", "fieldtype": "Data", "width": 180},
        {"label": _("业务员"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 120},
        {"label": _("开票日期"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 100},
        {"label": _("收款日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
        {"label": _("是否开发票"), "fieldname": "is_invoiced", "fieldtype": "Data", "width": 95},
        {"label": _("收款状态"), "fieldname": "receipt_status", "fieldtype": "Data", "width": 105},
    ]


def get_data(filters):
    conditions = ["pe.docstatus = 1", "pe.payment_type = 'Receive'"]
    if filters.get("company"):
        conditions.append("pe.company = %(company)s")
    if filters.get("customer"):
        conditions.append("pe.party = %(customer)s")
    if filters.get("from_date"):
        conditions.append("pe.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("pe.posting_date <= %(to_date)s")
    rows = frappe.db.sql(
        f"""
        SELECT YEAR(pe.posting_date) AS year, MONTH(pe.posting_date) AS month,
            COALESCE(si.customer, so.customer, pe.party) AS customer,
            COALESCE(si.customer_name, so.customer_name, pe.party_name) AS customer_name,
            COALESCE(si.grand_total, so.grand_total, pe.received_amount) AS grand_total,
            CASE
                WHEN per.reference_doctype = 'Sales Order'
                    THEN GREATEST(so.grand_total - COALESCE(so_receipts.received_amount, 0), 0)
                ELSE si.outstanding_amount
            END AS outstanding_amount,
            COALESCE(
                si.due_date,
                (
                    SELECT sop.due_date
                    FROM `tabPayment Schedule` sop
                    WHERE sop.parent = so.name
                    ORDER BY ABS(COALESCE(sop.payment_amount, 0) - COALESCE(per.allocated_amount, pe.received_amount)), sop.idx
                    LIMIT 1
                )
            ) AS due_date,
            COALESCE(si.posting_date, so.transaction_date) AS invoice_date,
            pe.posting_date,
            COALESCE(per.allocated_amount, pe.received_amount) AS received_amount,
            si.name AS sales_invoice, per.reference_doctype,
            MIN(sii.delivery_note) AS delivery_note,
            CASE WHEN per.reference_doctype = 'Sales Order' THEN per.reference_name ELSE MIN(sii.sales_order) END AS sales_order,
            MIN(COALESCE(invoice_item.custom_internal_model, order_item.custom_internal_model)) AS internal_model,
            MIN(COALESCE(invoice_item.custom_external_model, order_item.custom_external_model)) AS external_model,
            COALESCE(
                (SELECT st.sales_person FROM `tabSales Team` st WHERE st.parent = si.name ORDER BY st.idx LIMIT 1),
                (SELECT st.sales_person FROM `tabSales Team` st WHERE st.parent = so.name ORDER BY st.idx LIMIT 1)
            ) AS sales_person
        FROM `tabPayment Entry` pe
        LEFT JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
        LEFT JOIN `tabSales Invoice` si
            ON per.reference_doctype = 'Sales Invoice' AND si.name = per.reference_name
        LEFT JOIN `tabSales Order` so
            ON per.reference_doctype = 'Sales Order' AND so.name = per.reference_name
        LEFT JOIN (
            SELECT per_so.reference_name AS sales_order, SUM(per_so.allocated_amount) AS received_amount
            FROM `tabPayment Entry Reference` per_so
            INNER JOIN `tabPayment Entry` pe_so ON pe_so.name = per_so.parent
            WHERE pe_so.docstatus = 1
              AND pe_so.payment_type = 'Receive'
              AND per_so.reference_doctype = 'Sales Order'
            GROUP BY per_so.reference_name
        ) so_receipts ON so_receipts.sales_order = so.name
        LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        LEFT JOIN `tabSales Order Item` soi
            ON per.reference_doctype = 'Sales Order' AND soi.parent = per.reference_name
        LEFT JOIN `tabItem` invoice_item ON invoice_item.name = sii.item_code
        LEFT JOIN `tabItem` order_item ON order_item.name = soi.item_code
        WHERE {' AND '.join(conditions)}
        GROUP BY pe.name, per.name, si.name
        ORDER BY pe.posting_date DESC, pe.name DESC
        """,
        filters,
        as_dict=True,
    )
    for row in rows:
        row.receivable_days = max(0, frappe.utils.date_diff(row.posting_date, row.due_date)) if row.due_date else 0
        row.credit_period = f"{row.invoice_date or ''} ~ {row.due_date or ''}" if row.due_date else ""
        row.is_invoiced = _("已开票") if row.sales_invoice else _("未开票")
        if row.reference_doctype == "Sales Order" or row.sales_invoice:
            row.receipt_status = _("已结清") if not flt(row.outstanding_amount) else _("未结清")
        else:
            row.receipt_status = _("未关联销售发票")
    return rows


def get_report_summary(data):
    return [
        {"label": _("回款笔数"), "value": len(data), "datatype": "Int"},
        {
            "label": _("本次回款金额"),
            "value": sum(flt(row.received_amount) for row in data),
            "datatype": "Currency",
            "indicator": "green",
        },
        {
            "label": _("已结清笔数"),
            "value": sum(1 for row in data if row.receipt_status == _("已结清")),
            "datatype": "Int",
            "indicator": "green",
        },
        {
            "label": _("未结清笔数"),
            "value": sum(1 for row in data if row.receipt_status == _("未结清")),
            "datatype": "Int",
            "indicator": "orange",
        },
    ]
