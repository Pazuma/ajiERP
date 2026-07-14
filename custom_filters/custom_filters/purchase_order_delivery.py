import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_purchase_order_delivery_details(purchase_order):
    validate_purchase_order_read_permission(purchase_order)
    return get_purchase_order_delivery_tree(purchase_order)


def validate_purchase_order_read_permission(purchase_order):
    if not purchase_order or not frappe.db.exists("Purchase Order", purchase_order):
        frappe.throw(_("未找到采购订单 {0}").format(purchase_order or ""))

    if not frappe.has_permission("Purchase Order", "read", doc=purchase_order):
        frappe.throw(_("缺少 Purchase Order 读取权限"), frappe.PermissionError)


def get_purchase_order_delivery_tree(purchase_order):
    items = frappe.get_all(
        "Purchase Order Item",
        filters={"parent": purchase_order},
        fields=["name", "idx", "item_code", "item_name", "qty", "uom", "schedule_date"],
        order_by="idx asc",
    )

    received_by_item = get_received_qty_by_po_item(purchase_order)
    deliveries_by_item = get_delivery_rows_by_po_item(purchase_order)

    rows = []
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

        rows.append(
            {
                "row_id": item_row_id,
                "parent_row_id": None,
                "indent": 0,
                "row_type": "po_item",
                "item_code": item.item_code,
                "item_name": item.item_name,
                "ordered_qty": ordered_qty,
                "received_qty": received_qty,
                "pending_qty": pending_qty,
                "uom": item.uom,
                "schedule_date": item.schedule_date,
                "delivery_no": f"共 {delivery_count} 次交货" if delivery_count else "未交货",
                "posting_date": None,
                "purchase_receipt": None,
            }
        )

        for idx, delivery in enumerate(deliveries, start=1):
            rows.append(
                {
                    "row_id": f"delivery:{item.name}:{delivery.purchase_receipt}:{delivery.receipt_item_idx}",
                    "parent_row_id": item_row_id,
                    "indent": 1,
                    "row_type": "delivery",
                    "item_code": None,
                    "item_name": None,
                    "ordered_qty": None,
                    "received_qty": flt(delivery.received_qty),
                    "pending_qty": None,
                    "uom": item.uom,
                    "schedule_date": None,
                    "delivery_no": f"交货{idx}",
                    "posting_date": delivery.posting_date,
                    "purchase_receipt": delivery.purchase_receipt,
                }
            )

    return rows


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
