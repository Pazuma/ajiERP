import frappe


QUERY_REGISTRY = {
    "get_recent_sales_orders": {
        "doctype": "Sales Order",
        "date_field": "transaction_date",
        "fields": ["name", "customer", "transaction_date", "grand_total", "status"],
        "link_route": "sales-order",
        "empty_label": "销售订单记录",
        "title": "销售订单",
        "row_template": "- 订单号: [{name}](/app/sales-order/{name}), 客户: {customer}, 日期: {transaction_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "订单编号": "name",
            "客户名称": "customer",
            "交易日期": "transaction_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_sales_invoices": {
        "doctype": "Sales Invoice",
        "date_field": "posting_date",
        "fields": ["name", "customer", "posting_date", "grand_total", "status"],
        "link_route": "sales-invoice",
        "empty_label": "销售发票",
        "title": "销售发票",
        "row_template": "- 发票号: [{name}](/app/sales-invoice/{name}), 客户: {customer}, 日期: {posting_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "发票编号": "name",
            "客户名称": "customer",
            "开票日期": "posting_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_purchase_receipts": {
        "doctype": "Purchase Receipt",
        "date_field": "posting_date",
        "fields": ["name", "supplier", "posting_date", "grand_total", "status"],
        "link_route": "purchase-receipt",
        "empty_label": "采购入库单",
        "title": "采购入库单",
        "row_template": "- 入库单号: [{name}](/app/purchase-receipt/{name}), 供应商: {supplier}, 日期: {posting_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "入库单编号": "name",
            "供应商名称": "supplier",
            "入库日期": "posting_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_delivery_notes": {
        "doctype": "Delivery Note",
        "date_field": "posting_date",
        "fields": ["name", "customer", "posting_date", "grand_total", "status"],
        "link_route": "delivery-note",
        "empty_label": "销售出库单",
        "title": "销售出库单",
        "row_template": "- 出库单号: [{name}](/app/delivery-note/{name}), 客户: {customer}, 日期: {posting_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "出库单编号": "name",
            "客户名称": "customer",
            "出库日期": "posting_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_supplier_quotations": {
        "doctype": "Supplier Quotation",
        "date_field": "transaction_date",
        "fields": ["name", "supplier", "transaction_date", "grand_total", "status"],
        "link_route": "supplier-quotation",
        "empty_label": "供应商报价记录",
        "title": "供应商报价",
        "row_template": "- 报价单号: [{name}](/app/supplier-quotation/{name}), 供应商: {supplier}, 日期: {transaction_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "报价单编号": "name",
            "供应商名称": "supplier",
            "报价日期": "transaction_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_purchase_orders": {
        "doctype": "Purchase Order",
        "date_field": "transaction_date",
        "fields": ["name", "supplier", "transaction_date", "grand_total", "status"],
        "link_route": "purchase-order",
        "empty_label": "采购订单记录",
        "title": "采购订单",
        "row_template": "- 订单号: [{name}](/app/purchase-order/{name}), 供应商: {supplier}, 日期: {transaction_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "采购订单编号": "name",
            "供应商名称": "supplier",
            "交易日期": "transaction_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
    "get_recent_purchase_invoices": {
        "doctype": "Purchase Invoice",
        "date_field": "posting_date",
        "fields": ["name", "supplier", "posting_date", "grand_total", "status"],
        "link_route": "purchase-invoice",
        "empty_label": "采购发票记录",
        "title": "采购发票",
        "row_template": "- 发票号: [{name}](/app/purchase-invoice/{name}), 供应商: {supplier}, 日期: {posting_date}, 金额: ￥{grand_total}, 状态: {status}\n",
        "data_map": {
            "采购发票编号": "name",
            "供应商名称": "supplier",
            "开票日期": "posting_date",
            "总金额(元)": "grand_total",
            "当前状态": "status",
        },
    },
}


def _safe_limit(limit, default=5, maximum=50):
    try:
        return min(int(limit) if limit else default, maximum)
    except Exception:
        return default


def _date_filters(date_field, start_date=None, end_date=None):
    if start_date and end_date:
        return {date_field: ["between", [start_date, end_date]]}
    if start_date:
        return {date_field: [">=", start_date]}
    if end_date:
        return {date_field: ["<=", end_date]}
    return {}


def _serialise_value(value):
    if value is None:
        return ""
    try:
        return float(value)
    except Exception:
        return str(value)


def query_recent_documents(config, limit=5, start_date=None, end_date=None):
    limit = _safe_limit(limit)
    filters = _date_filters(config["date_field"], start_date, end_date)
    rows = frappe.db.get_list(
        config["doctype"],
        fields=config["fields"],
        filters=filters,
        order_by="creation desc",
        limit=limit,
    )
    if not rows:
        return {
            "text": f"报告：在指定范围内（{start_date or '未知'} 至 {end_date or '未知'}）没有找到任何{config['empty_label']}。",
            "data": [],
        }

    result = f"以下是从 ERPNext 数据库中查到的{config['title']}（受性能安全阀保护，最高展示前 {limit} 条）：\n"
    data = []
    for row in rows:
        values = {field: getattr(row, field, "") for field in config["fields"]}
        result += config["row_template"].format(**values)
        data_row = {}
        for label, fieldname in config["data_map"].items():
            value = getattr(row, fieldname, None)
            if fieldname in {"transaction_date", "posting_date"}:
                value = str(value)
            elif fieldname == "grand_total":
                value = float(value or 0)
            else:
                value = _serialise_value(value)
            data_row[label] = value
        data.append(data_row)
    return {"text": result, "data": data}


def query_recent_documents_by_name(function_name, limit=5, start_date=None, end_date=None):
    config = QUERY_REGISTRY[function_name]
    return query_recent_documents(config, limit=limit, start_date=start_date, end_date=end_date)

