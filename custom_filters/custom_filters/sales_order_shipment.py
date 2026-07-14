import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_sales_order_shipment_details(sales_order):
    validate_sales_order_read_permission(sales_order)
    return get_sales_order_shipment_tree(sales_order)


def validate_sales_order_read_permission(sales_order):
    if not sales_order or not frappe.db.exists("Sales Order", sales_order):
        frappe.throw(_("未找到销售订单 {0}").format(sales_order or ""))

    if not frappe.has_permission("Sales Order", "read", doc=sales_order):
        frappe.throw(_("缺少 Sales Order 读取权限"), frappe.PermissionError)


def get_sales_order_shipment_tree(sales_order):
    items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": sales_order},
        fields=["name", "idx", "item_code", "item_name", "qty", "uom", "delivery_date"],
        order_by="idx asc",
    )

    delivered_by_item = get_delivered_qty_by_so_item(sales_order)
    shipments_by_item = get_shipment_rows_by_so_item(sales_order)

    rows = []
    for item in items:
        ordered_qty = flt(item.qty)
        delivered_qty = flt(delivered_by_item.get(item.name, 0))
        pending_qty = max(ordered_qty - delivered_qty, 0)

        item_row_id = f"so_item:{item.name}"
        shipments = [
            shipment
            for shipment in shipments_by_item.get(item.name, [])
            if frappe.has_permission("Delivery Note", "read", doc=shipment.delivery_note)
        ]
        shipment_count = len(shipments)

        rows.append(
            {
                "row_id": item_row_id,
                "parent_row_id": None,
                "indent": 0,
                "row_type": "so_item",
                "item_code": item.item_code,
                "item_name": item.item_name,
                "ordered_qty": ordered_qty,
                "delivered_qty": delivered_qty,
                "pending_qty": pending_qty,
                "uom": item.uom,
                "schedule_date": item.delivery_date,
                "delivery_no": f"共 {shipment_count} 次出货" if shipment_count else "未出货",
                "posting_date": None,
                "delivery_note": None,
            }
        )

        for idx, shipment in enumerate(shipments, start=1):
            rows.append(
                {
                    "row_id": f"shipment:{item.name}:{shipment.delivery_note}:{shipment.dn_item_idx}",
                    "parent_row_id": item_row_id,
                    "indent": 1,
                    "row_type": "shipment",
                    "item_code": None,
                    "item_name": None,
                    "ordered_qty": None,
                    "delivered_qty": flt(shipment.delivered_qty),
                    "pending_qty": None,
                    "uom": item.uom,
                    "schedule_date": None,
                    "delivery_no": f"出货{idx}",
                    "posting_date": shipment.posting_date,
                    "delivery_note": shipment.delivery_note,
                }
            )

    return rows


def get_delivered_qty_by_so_item(sales_order):
    rows = frappe.db.sql(
        """
        select
            dni.so_detail,
            sum(dni.qty) as delivered_qty
        from `tabDelivery Note Item` dni
        inner join `tabDelivery Note` dn on dn.name = dni.parent
        where
            dn.docstatus = 1
            and dni.against_sales_order = %s
            and dni.so_detail is not null
            and char_length(dni.so_detail) > 0
            and ifnull(dni.qty, 0) > 0
        group by dni.so_detail
        """,
        (sales_order,),
        as_dict=True,
    )
    return {row.so_detail: flt(row.delivered_qty) for row in rows}


def get_shipment_rows_by_so_item(sales_order):
    rows = frappe.db.sql(
        """
        select
            soi.name as so_detail,
            dn.name as delivery_note,
            dn.posting_date,
            dn.posting_time,
            dni.idx as dn_item_idx,
            dni.qty as delivered_qty
        from `tabDelivery Note Item` dni
        inner join `tabDelivery Note` dn on dn.name = dni.parent
        inner join `tabSales Order Item` soi on soi.name = dni.so_detail
        where
            dn.docstatus = 1
            and dni.against_sales_order = %s
            and dni.so_detail is not null
            and char_length(dni.so_detail) > 0
            and ifnull(dni.qty, 0) > 0
        order by soi.idx asc, dn.posting_date asc, dn.posting_time asc, dn.name asc, dni.idx asc
        """,
        (sales_order,),
        as_dict=True,
    )

    result = {}
    for row in rows:
        result.setdefault(row.so_detail, []).append(row)

    return result
