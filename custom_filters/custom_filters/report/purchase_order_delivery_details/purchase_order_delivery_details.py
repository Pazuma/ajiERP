import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get("purchase_order"):
        return get_columns(), []

    return get_columns(), get_data(filters.purchase_order)


def get_columns():
    return [
        {"label": "序号", "fieldname": "idx", "fieldtype": "Int", "width": 60},
        {
            "label": "单号",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 150,
        },
        {"label": "订单日期", "fieldname": "transaction_date", "fieldtype": "Date", "width": 105},
        {"label": "供应商", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 130},
        {"label": "物料编码", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "物料名称", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "单位", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "订单数量", "fieldname": "order_qty", "fieldtype": "Float", "width": 95},
        {"label": "最新交期", "fieldname": "schedule_date", "fieldtype": "Date", "width": 105},
        {"label": "交货次数", "fieldname": "delivery_no", "fieldtype": "Data", "width": 90},
        {"label": "交货数量", "fieldname": "delivery_qty", "fieldtype": "Float", "width": 95},
        {"label": "交货日期", "fieldname": "delivery_date", "fieldtype": "Date", "width": 105},
        {
            "label": "采购收货单",
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 150,
        },
        {"label": "已交", "fieldname": "received_qty", "fieldtype": "Float", "width": 90},
        {"label": "未交", "fieldname": "pending_qty", "fieldtype": "Float", "width": 90},
    ]


def get_data(purchase_order):
    po = frappe.get_cached_doc("Purchase Order", purchase_order)
    items = frappe.get_all(
        "Purchase Order Item",
        filters={"parent": purchase_order},
        fields=["name", "idx", "item_code", "item_name", "qty", "uom", "schedule_date"],
        order_by="idx asc",
    )

    received_by_item = get_received_qty_by_po_item(purchase_order)
    deliveries_by_item = get_delivery_rows_by_po_item(purchase_order)

    data = []
    for item in items:
        ordered_qty = flt(item.qty)
        received_qty = flt(received_by_item.get(item.name, 0))
        pending_qty = max(ordered_qty - received_qty, 0)
        item_row_id = f"po_item:{item.name}"
        deliveries = [
            delivery
            for delivery in deliveries_by_item.get(item.name, [])
            if frappe.has_permission("Purchase Receipt", "read", doc=delivery.purchase_receipt)
        ]
        delivery_count = len(deliveries)

        data.append(
            {
                "idx": item.idx,
                "purchase_order": po.name,
                "transaction_date": po.transaction_date,
                "supplier": po.supplier,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.uom,
                "order_qty": ordered_qty,
                "schedule_date": item.schedule_date,
                "delivery_no": f"共 {delivery_count} 次交货" if delivery_count else "未交货",
                "delivery_qty": None,
                "delivery_date": None,
                "purchase_receipt": None,
                "received_qty": received_qty,
                "pending_qty": pending_qty,
                "row_id": item_row_id,
                "parent_row_id": None,
                "indent": 0,
            }
        )

        for idx, delivery in enumerate(deliveries, start=1):
            data.append(
                {
                    "idx": None,
                    "purchase_order": None,
                    "transaction_date": None,
                    "supplier": None,
                    "item_code": None,
                    "item_name": None,
                    "uom": item.uom,
                    "order_qty": None,
                    "schedule_date": None,
                    "delivery_no": f"交货{idx}",
                    "delivery_qty": flt(delivery.received_qty),
                    "delivery_date": delivery.posting_date,
                    "purchase_receipt": delivery.purchase_receipt,
                    "received_qty": None,
                    "pending_qty": None,
                    "row_id": f"delivery:{item.name}:{delivery.purchase_receipt}:{delivery.receipt_item_idx}",
                    "parent_row_id": item_row_id,
                    "indent": 1,
                }
            )

    return data


def get_received_qty_by_po_item(purchase_order):
    rows = frappe.db.sql(
        """
        select
            pri.purchase_order_item,
            sum(pri.qty) as received_qty
        from `tabPurchase Receipt Item` pri
        inner join `tabPurchase Receipt` pr on pr.name = pri.parent
        where
            pr.docstatus = 1
            and pri.purchase_order = %s
            and pri.purchase_order_item is not null
            and char_length(pri.purchase_order_item) > 0
            and ifnull(pri.qty, 0) > 0
        group by pri.purchase_order_item
        """,
        (purchase_order,),
        as_dict=True,
    )
    return {row.purchase_order_item: flt(row.received_qty) for row in rows}


def get_delivery_rows_by_po_item(purchase_order):
    rows = frappe.db.sql(
        """
        select
            poi.name as po_detail,
            pr.name as purchase_receipt,
            pr.posting_date,
            pr.posting_time,
            pri.idx as receipt_item_idx,
            pri.qty as received_qty
        from `tabPurchase Receipt Item` pri
        inner join `tabPurchase Receipt` pr on pr.name = pri.parent
        inner join `tabPurchase Order Item` poi on poi.name = pri.purchase_order_item
        where
            pr.docstatus = 1
            and pri.purchase_order = %s
            and pri.purchase_order_item is not null
            and char_length(pri.purchase_order_item) > 0
            and ifnull(pri.qty, 0) > 0
        order by poi.idx asc, pr.posting_date asc, pr.posting_time asc, pr.name asc, pri.idx asc
        """,
        (purchase_order,),
        as_dict=True,
    )

    result = {}
    for row in rows:
        result.setdefault(row.po_detail, []).append(row)

    return result
