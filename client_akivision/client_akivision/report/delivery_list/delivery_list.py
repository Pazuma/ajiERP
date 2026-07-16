import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    data = get_data(filters)
    return get_columns(), data, None, None, get_report_summary(data), 1


def get_report_summary(data):
    """Summarise only delivery-note and item rows, never duplicated tree parents."""
    sales_orders = {row.get("name") for row in data if row.get("indent") == 0 and not row.get("name", "").startswith("NO-SO#")}
    delivery_notes = {row.get("delivery_note") for row in data if row.get("indent") == 1 and row.get("delivery_note")}
    item_rows = [row for row in data if row.get("indent") == 2]
    completed_notes = sum(1 for row in data if row.get("indent") == 1 and row.get("order_status") == "已完成")

    return [
        {"value": len(sales_orders), "label": _("销售订单数"), "datatype": "Int", "indicator": "Blue"},
        {"value": len(delivery_notes), "label": _("送货单数"), "datatype": "Int", "indicator": "Blue"},
        {"value": sum(flt(row.get("qty")) for row in item_rows), "label": _("送货数量"), "datatype": "Float", "indicator": "Green"},
        {"value": sum(flt(row.get("amount")) for row in item_rows), "label": _("送货金额"), "datatype": "Currency", "indicator": "Green"},
        {"value": completed_notes, "label": _("已完成送货单"), "datatype": "Int", "indicator": "Green"},
    ]


def get_columns():
    return [
        {"label": _("销售订单 / 送货单 / 产品代码"), "fieldname": "name", "fieldtype": "Data", "width": 220},
        {"label": _("年份"), "fieldname": "year", "fieldtype": "Int", "width": 70},
        {"label": _("月份"), "fieldname": "month", "fieldtype": "Int", "width": 70},
        {"label": _("客户"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("客户代码"), "fieldname": "customer_code", "fieldtype": "Data", "width": 110},
        {"label": _("日期"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("业务员"), "fieldname": "sales_person", "fieldtype": "Link", "options": "Sales Person", "width": 120},
        {"label": _("客户订单号"), "fieldname": "customer_po_no", "fieldtype": "Data", "width": 150},
        {"label": _("产品代码"), "fieldname": "product_code", "fieldtype": "Link", "options": "Item", "width": 130},
        {"label": _("型号"), "fieldname": "model", "fieldtype": "Data", "width": 180},
        {"label": _("单位"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
        {"label": _("数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
        {"label": _("含税单价"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
        {"label": _("订单金额"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": _("送货单号"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 140},
        {"label": _("发票号"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 140},
        {"label": _("开票日期"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 100},
        {"label": _("订单状态"), "fieldname": "order_status", "fieldtype": "Data", "width": 110},
        {"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    delivery_notes = frappe.db.sql(
        f"""
        SELECT dn.name, dn.posting_date, dn.customer, dn.customer_name, dn.po_no, dn.status, dn.custom_remarks
        FROM `tabDelivery Note` dn
        WHERE dn.docstatus = 1 {conditions}
        ORDER BY dn.posting_date DESC, dn.name DESC
        """,
        filters,
        as_dict=True,
    )
    if not delivery_notes:
        return []

    dn_names = [row.name for row in delivery_notes]
    items_by_dn = {}
    sales_order_names = set()
    item_codes = set()
    dn_item_names = []
    for row in frappe.db.sql(
        """
        SELECT name, parent, idx, item_code, stock_uom AS uom, qty, rate, amount,
            against_sales_order, description
        FROM `tabDelivery Note Item`
        WHERE parent IN %(dn_names)s
        ORDER BY parent, idx
        """,
        {"dn_names": dn_names},
        as_dict=True,
    ):
        if filters.get("item_code") and row.item_code != filters.item_code:
            continue
        items_by_dn.setdefault(row.parent, []).append(row)
        item_codes.add(row.item_code)
        dn_item_names.append(row.name)
        if row.against_sales_order:
            sales_order_names.add(row.against_sales_order)

    if not items_by_dn:
        return []

    sales_orders = {
        row.name: row
        for row in frappe.db.get_all(
            "Sales Order",
            filters={"name": ["in", list(sales_order_names)]},
            fields=["name", "transaction_date", "customer", "customer_name", "po_no", "status", "custom_remarks"],
        )
    }
    models = {
        row.name: row.custom_external_model
        for row in frappe.db.get_all(
            "Item", filters={"name": ["in", list(item_codes)]}, fields=["name", "custom_external_model"]
        )
    }
    sales_people = get_sales_people(dn_names)
    invoices = get_invoices(dn_item_names)

    data = []
    added_roots = set()
    added_delivery_nodes = set()
    for dn in delivery_notes:
        dn_items = items_by_dn.get(dn.name, [])
        if not dn_items:
            continue

        by_sales_order = {}
        for item in dn_items:
            by_sales_order.setdefault(item.against_sales_order or None, []).append(item)

        for sales_order_name, grouped_items in by_sales_order.items():
            sales_order = sales_orders.get(sales_order_name)
            root_name = sales_order_name or f"NO-SO#{dn.name}"
            if root_name not in added_roots:
                added_roots.add(root_name)
                root_date = sales_order.transaction_date if sales_order else dn.posting_date
                root_customer = sales_order.customer if sales_order else dn.customer
                data.append(
                    make_row(
                        name=root_name,
                        indent=0,
                        is_group=1,
                        date=root_date,
                        customer=root_customer,
                        customer_code=root_customer,
                        customer_po_no=(sales_order.po_no if sales_order else dn.po_no),
                        order_status=translate_status(sales_order.status if sales_order else "未关联销售订单"),
                        remarks=(sales_order.custom_remarks if sales_order else ""),
                    )
                )

            delivery_node = f"{root_name}#{dn.name}"
            if delivery_node not in added_delivery_nodes:
                added_delivery_nodes.add(delivery_node)
                data.append(
                    make_row(
                        name=delivery_node,
                        name_display=dn.name,
                        parent=root_name,
                        indent=1,
                        is_group=1,
                        date=dn.posting_date,
                        customer=dn.customer,
                        customer_code=dn.customer,
                        sales_person=sales_people.get(dn.name),
                        customer_po_no=dn.po_no,
                        delivery_note=dn.name,
                        order_status=translate_status(dn.status),
                        remarks=dn.custom_remarks,
                    )
                )

            for item in grouped_items:
                invoice = invoices.get(item.name, {})
                data.append(
                    make_row(
                        name=f"{delivery_node}#{item.name}",
                        name_display=item.item_code,
                        parent=delivery_node,
                        indent=2,
                        date=dn.posting_date,
                        customer=dn.customer,
                        customer_code=dn.customer,
                        sales_person=sales_people.get(dn.name),
                        customer_po_no=dn.po_no,
                        product_code=item.item_code,
                        model=models.get(item.item_code),
                        uom=item.uom,
                        qty=flt(item.qty),
                        rate=flt(item.rate),
                        amount=flt(item.amount),
                        delivery_note=dn.name,
                        invoice_no=invoice.get("invoice_no"),
                        invoice_date=invoice.get("invoice_date"),
                    )
                )
    return data


def translate_status(status):
    """Translate ERPNext workflow status values for display."""
    if not status:
        return ""
    status_map = {
        "Draft": "草稿",
        "On Hold": "已冻结",
        "To Deliver and Bill": "待送货和开票",
        "To Bill": "待开票",
        "To Deliver": "待送货",
        "Completed": "已完成",
        "Cancelled": "已取消",
        "Closed": "已关闭",
        "未关联销售订单": "未关联销售订单",
    }
    return status_map.get(status) or _(status)


def make_row(**values):
    date = values.get("date")
    if date:
        date = getdate(date)
        values["year"] = date.year
        values["month"] = date.month
    return values


def get_sales_people(dn_names):
    result = {}
    for row in frappe.db.sql(
        """
        SELECT parent, sales_person
        FROM `tabSales Team`
        WHERE parenttype = 'Delivery Note' AND parent IN %(dn_names)s
        ORDER BY parent, idx
        """,
        {"dn_names": dn_names},
        as_dict=True,
    ):
        result.setdefault(row.parent, row.sales_person)
    return result


def get_invoices(dn_item_names):
    if not dn_item_names:
        return {}
    return {
        row.dn_detail: row
        for row in frappe.db.sql(
            """
            SELECT sii.dn_detail,
                GROUP_CONCAT(DISTINCT si.name ORDER BY si.posting_date SEPARATOR ', ') AS invoice_no,
                MAX(si.posting_date) AS invoice_date
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE sii.dn_detail IN %(dn_item_names)s AND si.docstatus = 1
            GROUP BY sii.dn_detail
            """,
            {"dn_item_names": dn_item_names},
            as_dict=True,
        )
    }


def get_conditions(filters):
    conditions = []
    if filters.get("company"):
        conditions.append("AND dn.company = %(company)s")
    if filters.get("customer"):
        conditions.append("AND dn.customer = %(customer)s")
    if filters.get("from_date"):
        conditions.append("AND dn.posting_date >= %(from_date)s")
    if filters.get("to_date"):
        conditions.append("AND dn.posting_date <= %(to_date)s")
    if filters.get("item_code"):
        conditions.append(
            "AND EXISTS (SELECT 1 FROM `tabDelivery Note Item` dni WHERE dni.parent = dn.name AND dni.item_code = %(item_code)s)"
        )
    return " ".join(conditions)
