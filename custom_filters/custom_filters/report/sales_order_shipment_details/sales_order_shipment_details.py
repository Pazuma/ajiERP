import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not filters.get("sales_order"):
        return get_columns(), []

    return get_columns(), get_data(filters.sales_order)


def get_columns():
    return [
        {"label": "序号", "fieldname": "idx", "fieldtype": "Int", "width": 60},
        {
            "label": "单号",
            "fieldname": "sales_order",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 150,
        },
        {"label": "订单日期", "fieldname": "transaction_date", "fieldtype": "Date", "width": 105},
        {"label": "客户", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 130},
        {"label": "物料编码", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "物料名称", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "单位", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
        {"label": "订单数量", "fieldname": "order_qty", "fieldtype": "Float", "width": 95},
        {"label": "最新交期", "fieldname": "schedule_date", "fieldtype": "Date", "width": 105},
        {"label": "出货次数", "fieldname": "delivery_no", "fieldtype": "Data", "width": 90},
        {"label": "出货数量", "fieldname": "delivery_qty", "fieldtype": "Float", "width": 95},
        {"label": "出货日期", "fieldname": "delivery_date", "fieldtype": "Date", "width": 105},
        {
            "label": "销售出库单",
            "fieldname": "delivery_note",
            "fieldtype": "Link",
            "options": "Delivery Note",
            "width": 150,
        },
        {"label": "已出", "fieldname": "delivered_qty", "fieldtype": "Float", "width": 90},
        {"label": "未出", "fieldname": "pending_qty", "fieldtype": "Float", "width": 90},
    ]


def get_data(sales_order):
    so = frappe.get_cached_doc("Sales Order", sales_order)
    items = frappe.get_all(
        "Sales Order Item",
        filters={"parent": sales_order},
        fields=["name", "idx", "item_code", "item_name", "qty", "uom", "delivery_date"],
        order_by="idx asc",
    )

    delivered_by_item = get_delivered_qty_by_so_item(sales_order)
    shipments_by_item = get_shipment_rows_by_so_item(sales_order)

    data = []
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

        data.append(
            {
                "idx": item.idx,
                "sales_order": so.name,
                "transaction_date": so.transaction_date,
                "customer": so.customer,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.uom,
                "order_qty": ordered_qty,
                "schedule_date": item.delivery_date,
                "delivery_no": f"共 {shipment_count} 次出货" if shipment_count else "未出货",
                "delivery_qty": None,
                "delivery_date": None,
                "delivery_note": None,
                "delivered_qty": delivered_qty,
                "pending_qty": pending_qty,
                "row_id": item_row_id,
                "parent_row_id": None,
                "indent": 0,
            }
        )

        for idx, shipment in enumerate(shipments, start=1):
            data.append(
                {
                    "idx": None,
                    "sales_order": None,
                    "transaction_date": None,
                    "customer": None,
                    "item_code": None,
                    "item_name": None,
                    "uom": item.uom,
                    "order_qty": None,
                    "schedule_date": None,
                    "delivery_no": f"出货{idx}",
                    "delivery_qty": flt(shipment.delivered_qty),
                    "delivery_date": shipment.posting_date,
                    "delivery_note": shipment.delivery_note,
                    "delivered_qty": None,
                    "pending_qty": None,
                    "row_id": f"shipment:{item.name}:{shipment.delivery_note}:{shipment.dn_item_idx}",
                    "parent_row_id": item_row_id,
                    "indent": 1,
                }
            )

    return data


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
