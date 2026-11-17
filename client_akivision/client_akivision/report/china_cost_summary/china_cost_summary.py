"""Invoice-basis financial reconciliation; never writes or recalculates costs."""
import frappe
from frappe.utils import flt, getdate
from client_akivision.client_akivision.api.operations_kpi_cost import normalise_cost_filters
from client_akivision.utils.operations_kpi_cost import read_rows, ratio
from client_akivision.utils.china_cost_summary_permissions import check_report_access


def posted_cost(entries):
    """Return outbound inventory cost as a positive amount.

    Stock Ledger Entry uses a negative value difference for sales issues;
    returns preserve their sign in the source and are handled separately.
    """
    return -sum(flt(row.get("stock_value_difference")) for row in entries) if entries else None


def allocate_cost(total, delivered_qty, invoiced_qty):
    if total is None or delivered_qty <= 0 or invoiced_qty <= 0 or invoiced_qty > delivered_qty + 0.000001:
        return None
    return total * invoiced_qty / delivered_qty


def ledger_cost(voucher_type, voucher, detail):
    if not frappe.has_permission("Stock Ledger Entry", "read"):
        return None
    if not frappe.has_permission(voucher_type, "read", doc=voucher):
        return None
    rows = read_rows("Stock Ledger Entry", {"voucher_type":voucher_type, "voucher_no":voucher,
        "voucher_detail_no":detail, "is_cancelled":0}, ["name", "stock_value_difference"])
    return posted_cost(rows)


def stock_ledger_source(voucher_type, voucher, detail):
    """Return traceable ledger names without exposing unrelated rows."""
    if not frappe.has_permission("Stock Ledger Entry", "read"):
        return []
    if not frappe.has_permission(voucher_type, "read", doc=voucher):
        return []
    return [row.name for row in read_rows("Stock Ledger Entry",
        {"voucher_type": voucher_type, "voucher_no": voucher,
         "voucher_detail_no": detail, "is_cancelled": 0}, ["name"])]


def invoice_rows(filters):
    if not frappe.has_permission("Sales Invoice", "read"):
        frappe.throw("无销售发票读取权限", frappe.PermissionError)
    invoices = read_rows("Sales Invoice", {"company":filters.company, "docstatus":1,
        "posting_date":["between",[filters.from_date,filters.to_date]]}, ["name"])
    result = []
    for record in invoices:
        doc = frappe.get_doc("Sales Invoice", record.name)
        doc.check_permission("read")
        for item in doc.items:
            if filters.get("sales_order") and item.sales_order != filters.sales_order:
                continue
            if item.sales_order and not frappe.has_permission("Sales Order", "read", doc=item.sales_order):
                continue
            if filters.get("work_order"):
                order = frappe.get_doc("Work Order", filters.work_order)
                order.check_permission("read")
                if not order.sales_order or order.sales_order != item.sales_order:
                    continue
            cost, reason = None, ""
            source = []
            cost_date = None
            if doc.is_return:
                reason = "红字/退货收入已冲减；成本冲回需逐笔核对"
            elif doc.update_stock:
                cost = ledger_cost("Sales Invoice", doc.name, item.name)
                source = stock_ledger_source("Sales Invoice", doc.name, item.name)
                cost_date = doc.posting_date if cost is not None else None
                if cost is None: reason = "未找到可读取的发票出库成本"
            elif item.delivery_note and item.dn_detail and frappe.has_permission("Delivery Note", "read", doc=item.delivery_note):
                delivery = frappe.get_doc("Delivery Note", item.delivery_note)
                detail = next((d for d in delivery.items if d.name == item.dn_detail), None)
                if delivery.docstatus != 1 or delivery.company != doc.company or delivery.is_return or not detail or detail.item_code != item.item_code:
                    reason = "交货单状态、产品或公司不匹配"
                else:
                    # Verify cumulative submitted billing, including outside selected period.
                    links = frappe.db.sql("""select sum(abs(i.stock_qty)) qty from `tabSales Invoice Item` i
                        join `tabSales Invoice` s on s.name=i.parent where s.docstatus=1
                        and s.is_return=0 and i.delivery_note=%s and i.dn_detail=%s""",
                        (delivery.name, detail.name), as_dict=True)[0]
                    if flt(links.qty) > flt(detail.stock_qty) + .000001:
                        reason = "累计开票数量超过交货数量，待核对"
                    else:
                        cost = allocate_cost(ledger_cost("Delivery Note", delivery.name, detail.name),
                                             flt(detail.stock_qty), flt(item.stock_qty))
                        source = stock_ledger_source("Delivery Note", delivery.name, detail.name)
                        cost_date = delivery.posting_date if cost is not None else None
                        if cost is None: reason = "缺少交货成本或有效库存数量"
            else:
                reason = "未关联可读取的交货明细，且非发票直接出库；服务及其他收入需人工核对"
            revenue = flt(item.base_net_amount)
            if not item.sales_order:
                reason = (reason + "；" if reason else "") + "未关联销售订单"
            if cost_date and str(cost_date)[:7] != str(doc.posting_date)[:7]:
                reason = (reason + "；" if reason else "") + "收入与成本跨月，需核对结转期间"
            result.append(dict(sales_order=item.sales_order, invoice=doc.name, date=doc.posting_date,
                cost_date=cost_date, delivery_note=item.delivery_note if item.delivery_note and frappe.has_permission("Delivery Note", "read", doc=item.delivery_note) else None,
                customer=doc.customer, item_code=item.item_code, qty=item.stock_qty, revenue=revenue,
                sales_cost=cost, profit=revenue-cost if cost is not None else None,
                margin=ratio(revenue-cost,revenue)*100 if cost is not None and revenue else None,
                status="已匹配" if cost is not None and not reason else "待核算", reason=reason,
                action="核对来源凭证、数量、人工及期间后重新查询" if reason else "",
                source=", ".join(source) or (doc.name if doc.update_stock else ""),
                currency=frappe.get_cached_value("Company",doc.company,"default_currency")))
    return result


def work_order_rows(filters):
    if not frappe.has_permission("Work Order", "read"):
        frappe.throw("无生产工单读取权限", frappe.PermissionError)
    wo_filters = {"company":filters.company, "docstatus":1}
    if filters.get("sales_order"): wo_filters["sales_order"] = filters.sales_order
    if filters.get("work_order"): wo_filters["name"] = filters.work_order
    orders = read_rows("Work Order", wo_filters, ["name"])
    result = []
    for record in orders:
        doc = frappe.get_doc("Work Order", record.name)
        doc.check_permission("read")
        if doc.sales_order and not frappe.has_permission("Sales Order", "read", doc=doc.sales_order):
            continue
        entries = read_rows("Stock Entry", {"company":filters.company,"docstatus":1,"purpose":"Manufacture",
            "work_order":doc.name,"posting_date":["between",[filters.production_from_date,filters.production_to_date]]}, ["name", "posting_date"])
        unfinished = doc.status != "Completed"
        if not entries and (not unfinished or (doc.planned_start_date and getdate(doc.planned_start_date)>filters.production_to_date)):
            continue
        amount = qty = additional = 0
        for entry in entries:
            se = frappe.get_doc("Stock Entry", entry.name)
            se.check_permission("read")
            additional += flt(se.total_additional_costs)
            for detail in se.items:
                if detail.is_finished_item:
                    amount += flt(detail.amount)
                    qty += flt(detail.transfer_qty)
        reasons = []
        if unfinished: reasons.append("未完工：单列工单，未计算期末在制金额")
        if not flt(doc.get("custom_actual_labor_cost")): reasons.append("实际人工为零，待确认是否漏录或无需发生")
        if not doc.sales_order: reasons.append("未关联销售订单，需确认备货生产")
        if not entries: reasons.append("本期无可读取的制造入库")
        if entries and not qty: reasons.append("制造凭证无有效成品入库数量")
        if doc.get("custom_parent_work_order"): reasons.append("子工单成本仅供追溯，不再加到根工单")
        result.append(dict(work_order=doc.name, parent_work_order=doc.get("custom_parent_work_order"),
            root_work_order=doc.get("custom_root_work_order") or (doc.name if not doc.get("custom_parent_work_order") else None),
            sales_order=doc.sales_order,item_code=doc.production_item,qty=qty,production_cost=amount if entries and qty else None,
            labor=doc.get("custom_actual_labor_cost"),unit_cost=ratio(amount,qty),
            additional_costs=additional if entries else None,
            currency=frappe.get_cached_value("Company", filters.company, "default_currency"),
            work_order_status=doc.status, production_dates=", ".join(sorted({str(e.posting_date) for e in entries})),
            action="核对工单、人工和制造入库；子工单仅追溯" if reasons else "",
            status="待核算" if reasons else "已匹配",reason="；".join(reasons),
            source=", ".join(e.name for e in entries)))
    return result


def columns(work=False):
    specs = [("sales_order","销售订单","Link","Sales Order"),
        ("work_order","生产工单","Link","Work Order"),
        ("parent_work_order","上层工单","Link","Work Order"),
        ("root_work_order","根工单","Link","Work Order")] if work else [
        ("sales_order","销售订单","Link","Sales Order"),("invoice","销售发票","Link","Sales Invoice"),
        ("date","开票过账日期","Date",None),("cost_date","成本过账日期","Date",None),
        ("delivery_note","交货单","Link","Delivery Note"),("customer","客户","Link","Customer")]
    if work:
        specs += [("production_dates","制造入库日期","Data",None), ("work_order_status","工单状态","Data",None)]
    specs += [("item_code","产品","Link","Item"),("qty","库存单位数量","Float",None)]
    specs += [("production_cost","本期成品入库成本","Currency",None),
        ("additional_costs","制造附加费用（仅展示）","Currency",None),
        ("labor","工单累计实际人工（仅展示）","Currency",None),("unit_cost","本期单位入库成本","Currency",None)] if work else [
        ("revenue","开票不含税收入","Currency",None),("sales_cost","对应销售成本","Currency",None),
        ("profit","毛利","Currency",None),("margin","毛利率 %","Percent",None)]
    specs += [("status","核算状态","Data",None),("reason","待核算原因","Data",None),("action","建议处理","Data",None),("source","来源凭证","Data",None)]
    return [dict(fieldname=k,label=label,fieldtype=kind,options="currency" if kind == "Currency" else options,width=180 if kind!="Currency" else 150)
            for k,label,kind,options in specs]


def pending_columns():
    """A stable superset for the cross-source exception view."""
    specs = [
        ("record_type", "来源类型", "Data", None),
        ("invoice", "销售发票", "Link", "Sales Invoice"),
        ("work_order", "生产工单", "Link", "Work Order"),
        ("sales_order", "销售订单", "Link", "Sales Order"),
        ("item_code", "产品", "Link", "Item"),
        ("qty", "数量", "Float", None),
        ("revenue", "开票不含税收入", "Currency", None),
        ("sales_cost", "销售成本", "Currency", None),
        ("production_cost", "生产成本", "Currency", None),
        ("labor", "实际人工", "Currency", None),
        ("status", "核算状态", "Data", None),
        ("reason", "待核算原因", "Data", None),
        ("action", "建议处理", "Data", None),
        ("source", "来源凭证", "Data", None),
    ]
    return [dict(fieldname=k, label=label, fieldtype=kind, options="currency" if kind == "Currency" else options,
                 width=180 if kind != "Currency" else 150)
            for k, label, kind, options in specs]


def pending_rows(filters):
    invoice_pending = [dict(record_type="销售", **row) for row in invoice_rows(filters)
                       if row["status"] == "待核算"]
    work_pending = [dict(record_type="生产", **row) for row in work_order_rows(filters)
                    if row["status"] == "待核算"]
    return invoice_pending + work_pending


def execute(filters=None):
    check_report_access()
    raw = frappe._dict(filters or {})
    filters = normalise_cost_filters(raw)
    filters.update({k:raw.get(k) for k in ("sales_order","work_order")})
    filters.production_from_date = getdate(raw.get("production_from_date") or filters.from_date)
    filters.production_to_date = getdate(raw.get("production_to_date") or filters.to_date)
    if filters.production_from_date > filters.production_to_date:
        frappe.throw("制造期间开始日期不能晚于截止日期。")
    for doctype, name in (("Sales Order", filters.sales_order), ("Work Order", filters.work_order)):
        if name:
            doc = frappe.get_doc(doctype, name)
            doc.check_permission("read")
            if doc.company != filters.company:
                frappe.throw("筛选单据与所选公司不一致。")
    view = raw.get("view") or "订单成本与毛利"
    if view not in ("订单成本与毛利", "工单成本", "待核算项"):
        frappe.throw("请选择有效核算视图。")
    work = view == "工单成本"
    if view == "待核算项":
        return pending_columns(), pending_rows(filters), (
            "待核算项同时汇总销售发票与生产工单；请按来源凭证下钻处理。")
    rows = work_order_rows(filters) if work else invoice_rows(filters)
    message = ("公司本位币；工单视图按本期制造入库及未完工工单展示，人工为工单累计值，已含人工不重复相加。"
        "订单视图逐发票明细展示，按开票过账期间；交货成本按库存数量比例匹配，未匹配成本与毛利留空。"
        "未完工非历史在制快照；不支持直接据此完成月结。分层工单不可跨层合计。")
    return columns(work), rows, message
