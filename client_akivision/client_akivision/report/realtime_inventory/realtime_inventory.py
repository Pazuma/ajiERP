import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.stock.report.stock_balance.stock_balance import execute as execute_stock_balance


def execute(filters=None):
    filters = frappe._dict(filters or {})
    company = filters.get("company") or frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("请先选择公司"))

    from_date = filters.get("from_date") or nowdate()
    to_date = filters.get("to_date") or nowdate()
    warehouse = filters.get("warehouse")
    item_group = filters.get("item_group")

    _columns, stock_rows = execute_stock_balance(
        frappe._dict(
            {
                "company": company,
                "from_date": from_date,
                "to_date": to_date,
                "item_group": item_group,
                "warehouse": [warehouse] if warehouse else None,
                "ignore_closing_balance": 0,
                "include_zero_stock_items": 0,
                "show_stock_ageing_data": 0,
                "show_variant_attributes": 0,
                "show_alt_uom_balance": 0,
            }
        )
    )

    in_transit = get_purchase_in_transit(company, to_date, warehouse, item_group)
    return get_columns(), summarize_by_item(stock_rows, to_date, in_transit)


def get_columns():
    return [
        {"label": "物料编码", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "物料名称", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
        {"label": "版本", "fieldname": "version", "fieldtype": "Data", "width": 70},
        {"label": "适用机种", "fieldname": "applicable_model", "fieldtype": "Data", "width": 100},
        {"label": "类别", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 100},
        {"label": "期初库存", "fieldname": "opening_qty", "fieldtype": "Float", "width": 100},
        {"label": "总入库", "fieldname": "in_qty", "fieldtype": "Float", "width": 90},
        {"label": "总出库", "fieldname": "out_qty", "fieldtype": "Float", "width": 90},
        {"label": "期末库存", "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
        {"label": "采购在途数量", "fieldname": "in_transit_qty", "fieldtype": "Float", "width": 110},
        {"label": "仓库", "fieldname": "warehouses", "fieldtype": "Data", "width": 180},
        {"label": "截止日期", "fieldname": "count_date", "fieldtype": "Date", "width": 100},
        {"label": "单位成本", "fieldname": "valuation_rate", "fieldtype": "Currency", "width": 100},
        {"label": "库存金额", "fieldname": "stock_value", "fieldtype": "Currency", "width": 110},
        {"label": "理论余数", "fieldname": "theoretical_qty", "fieldtype": "Float", "width": 100},
        {"label": "差值", "fieldname": "difference_qty", "fieldtype": "Float", "width": 80},
    ]


def get_purchase_in_transit(company, to_date, warehouse=None, item_group=None):
    conditions = [
        "po.docstatus = 1",
        "po.status != 'Closed'",
        "po.company = %(company)s",
        "po.transaction_date <= %(to_date)s",
    ]
    params = {"company": company, "to_date": to_date}
    if warehouse:
        conditions.append("poi.warehouse = %(warehouse)s")
        params["warehouse"] = warehouse
    if item_group:
        conditions.append("i.item_group = %(item_group)s")
        params["item_group"] = item_group

    rows = frappe.db.sql(
        f"""SELECT poi.item_code, SUM(GREATEST(poi.qty - IFNULL(poi.received_qty, 0), 0)) AS in_transit_qty
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        INNER JOIN `tabItem` i ON i.name = poi.item_code
        WHERE {' AND '.join(conditions)}
        GROUP BY poi.item_code
        HAVING SUM(GREATEST(poi.qty - IFNULL(poi.received_qty, 0), 0)) > 0""",
        params,
        as_dict=True,
    )
    return {row.item_code: flt(row.in_transit_qty) for row in rows}


def summarize_by_item(stock_rows, to_date, in_transit=None):
    in_transit = in_transit or {}
    item_codes = list({row.item_code for row in stock_rows} | set(in_transit))
    if not item_codes:
        return []

    item_fields = ["name"]
    item_meta = frappe.get_meta("Item")
    if item_meta.has_field("custom_version"):
        item_fields.append("custom_version")
    if item_meta.has_field("custom_applicable_model"):
        item_fields.append("custom_applicable_model")

    item_details = {
        row.name: row
        for row in frappe.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=item_fields,
        )
    }

    summary = {}
    for row in stock_rows:
        data = summary.setdefault(
            row.item_code,
            frappe._dict(
                {
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "version": item_details.get(row.item_code, {}).get("custom_version") or "",
                    "applicable_model": item_details.get(row.item_code, {}).get("custom_applicable_model") or "",
                    "item_group": row.item_group,
                    "opening_qty": 0.0,
                    "in_qty": 0.0,
                    "out_qty": 0.0,
                    "actual_qty": 0.0,
                    "stock_value": 0.0,
                    "warehouses": [],
                    "count_date": to_date,
                    "in_transit_qty": flt(in_transit.get(row.item_code, 0)),
                },
            ),
        )
        data.opening_qty += flt(row.opening_qty)
        data.in_qty += flt(row.in_qty)
        data.out_qty += flt(row.out_qty)
        data.actual_qty += flt(row.bal_qty)
        data.stock_value += flt(row.bal_val)
        if row.warehouse:
            data.warehouses.append(row.warehouse)

    result = []
    for row in summary.values():
        row.warehouses = ", ".join(sorted(set(row.warehouses)))
        row.valuation_rate = flt(row.stock_value / row.actual_qty) if row.actual_qty else 0.0
        row.theoretical_qty = flt(row.opening_qty + row.in_qty - row.out_qty)
        row.difference_qty = flt(row.actual_qty - row.theoretical_qty)
        result.append(row)

    for item_code, qty in in_transit.items():
        if item_code in summary:
            continue
        item = frappe.db.get_value("Item", item_code, ["item_name", "item_group"], as_dict=True) or {}
        details = item_details.get(item_code, {})
        result.append(
            frappe._dict(
                {
                    "item_code": item_code,
                    "item_name": item.get("item_name") or item_code,
                    "version": details.get("custom_version") or "",
                    "applicable_model": details.get("custom_applicable_model") or "",
                    "item_group": item.get("item_group") or "",
                    "opening_qty": 0.0,
                    "in_qty": 0.0,
                    "out_qty": 0.0,
                    "actual_qty": 0.0,
                    "stock_value": 0.0,
                    "warehouses": "",
                    "count_date": to_date,
                    "valuation_rate": 0.0,
                    "theoretical_qty": 0.0,
                    "difference_qty": 0.0,
                    "in_transit_qty": flt(qty),
                }
            )
        )

    return sorted(result, key=lambda row: row.item_code)
