"""Read-only cost analytics. Never refresh or write business documents."""
from collections import defaultdict

import frappe
from frappe.utils import flt, now_datetime

MAX_ROWS = 20000


def metric(value=None, datatype="Percent", reason="", status=None):
    return {"value": value, "datatype": datatype,
            "status": status or ("available" if value is not None else "not_configured"), "reason": reason}


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def variance(actual_price, standard_price, actual_qty, allowed_qty):
    """Amounts reconcile exactly; allowed quantity uses actual good output."""
    return {"price": (actual_price - standard_price) * actual_qty,
            "usage": (actual_qty - allowed_qty) * standard_price,
            "total": actual_price * actual_qty - standard_price * allowed_qty}


def read_rows(doctype, filters, fields):
    # get_list applies Frappe document and User Permission filters, unlike raw SQL/get_all.
    rows = frappe.get_list(doctype, filters=filters, fields=fields,
                           order_by="name", limit_page_length=MAX_ROWS + 1)
    if len(rows) > MAX_ROWS:
        frappe.throw("成本数据超过单次分析上限（20000行），请缩小日期范围；未返回截断汇总。")
    return rows


def financial_data(filters):
    if not frappe.has_permission("Account", "read") or not frappe.has_permission("GL Entry", "read"):
        return [], [], "缺少科目或总账读取权限"
    accounts = read_rows("Account", {"company": filters.company, "is_group": 0,
                         "account_type": ["in", ["Direct Income", "Income Account", "Cost of Goods Sold"]]},
                         ["name", "account_type"])
    types = {a.name: a.account_type for a in accounts}
    if not types or "Cost of Goods Sold" not in types.values() or not any(
        kind != "Cost of Goods Sold" for kind in types.values()
    ):
        return [], accounts, "未找到完整的收入与销售成本科目类型，请财务核对科目配置"
    rows = read_rows("GL Entry", {"company": filters.company,
                     "posting_date": ["between", [filters.from_date, filters.to_date]],
                     "is_cancelled": 0, "is_opening": "No",
                     "voucher_type": ["!=", "Period Closing Voucher"], "account": ["in", list(types)]},
                     ["name", "posting_date", "account", "debit", "credit"])
    periods = defaultdict(lambda: {"revenue": 0, "sales_cost": 0, "entries": 0})
    for row in rows:
        period = periods[str(row.posting_date)[:7]]
        key = "sales_cost" if types[row.account] == "Cost of Goods Sold" else "revenue"
        period[key] += flt(row.debit) - flt(row.credit) if key == "sales_cost" else flt(row.credit) - flt(row.debit)
        period["entries"] += 1
    return [{"period": month, **values, "gross_profit": values["revenue"] - values["sales_cost"]}
            for month, values in sorted(periods.items())], accounts, ""


def production_data(filters):
    if not frappe.has_permission("Stock Entry", "read") or not frappe.has_permission("Work Order", "read"):
        return [], 0, "缺少生产工单或库存凭证读取权限"
    # Root orders only: child assembly value is already embedded in consumed semi-finished stock.
    wo_filters = {"company": filters.company, "docstatus": 1}
    has_parent = frappe.db.has_column("Work Order", "custom_parent_work_order")
    work_orders = read_rows("Work Order", wo_filters,
                           ["name"] + (["custom_parent_work_order"] if has_parent else []))
    roots = [w.name for w in work_orders if not w.get("custom_parent_work_order")]
    if not roots:
        return [], 0, "所选公司没有可读取的根生产工单"
    entries = read_rows("Stock Entry", {"company": filters.company, "docstatus": 1,
                        "purpose": "Manufacture", "work_order": ["in", roots],
                        "posting_date": ["between", [filters.from_date, filters.to_date]]},
                        ["name", "work_order", "posting_date"])
    products = defaultdict(lambda: {"qty": 0, "production_cost": 0, "entries": set()})
    # Child table reads must be constrained to already-authorized parent names.
    for start in range(0, len(entries), 500):
        names = [e.name for e in entries[start:start + 500]]
        details = frappe.get_all("Stock Entry Detail", filters={"parent": ["in", names],
            "parenttype": "Stock Entry", "is_finished_item": 1},
            fields=["parent", "item_code", "stock_uom", "transfer_qty", "amount"], limit_page_length=MAX_ROWS + 1)
        if len(details) > MAX_ROWS:
            frappe.throw("生产成本明细超限，请缩小日期范围。")
        for row in details:
            product = products[(row.item_code, row.stock_uom)]
            product["qty"] += flt(row.transfer_qty)
            product["production_cost"] += flt(row.amount)
            product["entries"].add(row.parent)
    result = []
    for (item, uom), values in sorted(products.items()):
        result.append({"item_code": item, "stock_uom": uom, "qty": values["qty"],
            "production_cost": values["production_cost"],
            "unit_cost": ratio(values["production_cost"], values["qty"]),
            "entry_count": len(values["entries"])})
    return result, len(entries), ""


def build_cost_dashboard_data(filters):
    trend, accounts, financial_reason = financial_data(filters)
    products, entry_count, production_reason = production_data(filters)
    revenue = sum(row["revenue"] for row in trend)
    cost = sum(row["sales_cost"] for row in trend)
    no_financial = financial_reason or ("所选期间无可读取的总账发生额" if not trend else "")
    reason = "参考口径：Direct Income / Income Account 与 Cost of Goods Sold 科目，财务尚需确认主营范围"
    metrics = {
        "gross_margin": metric(ratio(revenue - cost, revenue) if not no_financial else None,
            reason=no_financial or (reason if revenue else "收入为零，无法计算毛利率"),
            status="reference" if revenue and not no_financial else "no_data"),
        "budget_execution": metric(reason="主营成本预算及科目映射尚未配置"),
        "rework_scrap_ratio": metric(reason="缺少独立返工/报废成本证据，未以异常损耗代替"),
        "unit_cost_variance": metric(reason="缺少经确认的历史标准成本快照、完工及试制识别规则"),
        "revenue": metric(None if no_financial else revenue, "Currency", no_financial or reason),
        "sales_cost": metric(None if no_financial else cost, "Currency", no_financial or reason),
        "gross_profit": metric(None if no_financial else revenue - cost, "Currency", no_financial or reason),
        "production_cost": metric(sum(r["production_cost"] for r in products) if products else None,
            "Currency", production_reason or "本期根工单制造入库成品金额，含已计入估值的附加费用；不是销售成本"),
    }
    start = (filters.page - 1) * filters.page_length
    return {"schema_version": "cost-v1", "filters": {key: str(filters[key]) for key in
            ("company", "from_date", "to_date")},
        "currency": frappe.get_cached_value("Company", filters.company, "default_currency"),
        "generated_at": str(now_datetime()), "metrics": metrics, "trend": trend,
        "product_rows": products[start:start + filters.page_length],
        "pagination": {"page": filters.page, "page_length": filters.page_length, "total": len(products)},
        "variance_rows": [], "structure": [],
        "coverage": {"manufacture_entries": entry_count, "standard_cost_included": 0},
        "accounts": [{"name": a.name, "account_type": a.account_type} for a in accounts],
        "warnings": [reason, "统计仅限当前用户可读取的数据；不保证等于全公司财务报表。",
            "产品表为本期根工单成品入库成本，不是产品销售毛利；不包含无工单制造入库。",
            "材料、人工、制造费用尚无可对账的独立拆分来源，成本结构暂不绘图。",
            "标准成本差异暂不着色：历史标准、预算和预警规则待确认。"]
            + [r for r in (financial_reason, production_reason) if r], "drilldowns": {}}
