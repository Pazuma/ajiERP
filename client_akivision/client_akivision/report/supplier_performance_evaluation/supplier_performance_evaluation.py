import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("请先选择公司"))

    from_date = getdate(filters.get("from_date") or nowdate())
    to_date = getdate(filters.get("to_date") or nowdate())

    data = get_data(from_date, to_date, company, filters.get("supplier"))
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_report_summary(data):
    purchase_order_count = sum(flt(row.purchase_order_count) for row in data)
    on_time_order_count = sum(flt(row.on_time_order_count) for row in data)
    delayed_order_count = sum(flt(row.delayed_order_count) for row in data)
    on_time_rate = (on_time_order_count / purchase_order_count * 100) if purchase_order_count else 0

    return [
        {"value": len(data), "label": _("供应商数"), "datatype": "Int", "indicator": "Blue"},
        {"value": purchase_order_count, "label": _("采购订单总数"), "datatype": "Int", "indicator": "Blue"},
        {"value": on_time_rate, "label": _("整体到货及时率"), "datatype": "Percent", "indicator": "Green"},
        {"value": delayed_order_count, "label": _("延迟订单数"), "datatype": "Int", "indicator": "Red"},
    ]


def get_columns():
    return [
        {"label": "供应商名称", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 200},
        {"label": "采购订单总数", "fieldname": "purchase_order_count", "fieldtype": "Int", "width": 120},
        {"label": "按时到货订单数", "fieldname": "on_time_order_count", "fieldtype": "Int", "width": 140},
        {"label": "到货及时率", "fieldname": "on_time_rate", "fieldtype": "Percent", "width": 120},
        {"label": "延迟订单数", "fieldname": "delayed_order_count", "fieldtype": "Int", "width": 120},
        {"label": "平均延迟天数", "fieldname": "average_delay_days", "fieldtype": "Float", "width": 120},
        {"label": "供应商评级", "fieldname": "supplier_rating", "fieldtype": "Data", "width": 100},
    ]


def get_data(from_date, to_date, company, supplier):
    return frappe.db.sql(
        """
        SELECT
            s.name AS supplier,
            COUNT(*) AS purchase_order_count,
            SUM(CASE WHEN po_status.max_delay_days = 0 THEN 1 ELSE 0 END) AS on_time_order_count,
            ROUND(SUM(CASE WHEN po_status.max_delay_days = 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 2) AS on_time_rate,
            SUM(CASE WHEN po_status.max_delay_days > 0 THEN 1 ELSE 0 END) AS delayed_order_count,
            ROUND(AVG(CASE WHEN po_status.max_delay_days > 0 THEN po_status.max_delay_days END), 2) AS average_delay_days,
            s.custom_supplier_rating AS supplier_rating
        FROM `tabSupplier` s
        INNER JOIN (
            SELECT
                po.name,
                po.supplier,
                MAX(
                    GREATEST(
                        COALESCE(receipt_delay.max_receipt_delay, 0),
                        CASE
                            WHEN IFNULL(poi.received_qty, 0) < poi.qty
                                THEN GREATEST(DATEDIFF(LEAST(%(to_date)s, CURDATE()), poi.schedule_date), 0)
                            ELSE 0
                        END
                    )
                ) AS max_delay_days
            FROM `tabPurchase Order` po
            INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
            LEFT JOIN (
                SELECT
                    pri.purchase_order_item,
                    MAX(GREATEST(DATEDIFF(pr.posting_date, poi_inner.schedule_date), 0)) AS max_receipt_delay
                FROM `tabPurchase Receipt` pr
                INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
                INNER JOIN `tabPurchase Order Item` poi_inner ON poi_inner.name = pri.purchase_order_item
                WHERE pr.docstatus = 1
                  AND pr.posting_date <= %(to_date)s
                GROUP BY pri.purchase_order_item
            ) receipt_delay ON receipt_delay.purchase_order_item = poi.name
            WHERE po.docstatus = 1
              AND po.company = %(company)s
              AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s
              AND (%(supplier)s IS NULL OR po.supplier = %(supplier)s)
            GROUP BY po.name, po.supplier
        ) po_status ON po_status.supplier = s.name
        GROUP BY s.name, s.supplier_name, s.custom_supplier_rating
        ORDER BY s.supplier_name
        """,
        {
            "from_date": from_date,
            "to_date": to_date,
            "company": company,
            "supplier": supplier or None,
        },
        as_dict=True,
    )
