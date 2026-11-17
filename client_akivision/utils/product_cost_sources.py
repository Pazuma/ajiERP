"""Source adapters. No recalculation, price synchronization or source writes."""
import json

import frappe
from frappe.utils import flt, now_datetime

from client_akivision.utils.product_cost_permissions import read_source, require_cost_user


def _refs(dt, name, row=None):
    return frappe.as_json([{"doctype": dt, "name": name, "row": row}])


def _expand_bom(name, company, factor=1, ancestors=()):
    if name in ancestors:
        frappe.throw("BOM循环引用：" + " → ".join((*ancestors, name)))
    bom = read_source("BOM", name, company)
    if flt(bom.quantity) <= 0:
        frappe.throw("BOM数量必须大于零")
    rows, operations = [], []
    scale = factor / flt(bom.quantity)
    for item in bom.get("items") or []:
        amount = flt(item.stock_qty) * scale
        if item.bom_no and not item.get("do_not_explode"):
            children, child_operations = _expand_bom(item.bom_no, company, amount, (*ancestors, name))
            rows.extend(children)
            operations.extend(child_operations)
        else:
            master = read_source("Item", item.item_code)
            rows.append({"item_code": item.item_code, "description": master.item_name,
                         "category": master.item_group, "qty_per_unit": amount,
                         "stock_uom": master.stock_uom, "purchase_uom": master.stock_uom,
                         "conversion_factor": 1, "price_basis": "Supplier Rule",
                         "price_exchange_rate": 1, "pack_multiple": 1, "loss_method": "None",
                         "surplus_policy": "Reusable", "source_key": "BOM:" + item.item_code,
                         "source_refs": _refs("BOM", name, item.name)})
    for operation in bom.get("operations") or []:
        # BOM time is per BOM output quantity unless explicitly fixed per batch.
        fixed = bool(operation.get("fixed_time"))
        hours = flt(operation.time_in_mins) / 60 * (1 if fixed else scale)
        operations.append({"operation": operation.operation, "workstation": operation.workstation,
                           "charging_basis": "Per Batch" if fixed else "Per Unit",
                           "standard_hours": hours, "hourly_rate": flt(operation.get("base_hour_rate")),
                           "included_cost_scope": "BOM工作站费率（请核实人工/设备包含范围）",
                           "source_key": f"BOMOP:{name}:{operation.name}",
                           "source_refs": _refs("BOM", name, operation.name)})
    return rows, operations


def _material_defaults(rows, doc):
    from custom_filters.item_supplier_pricing import get_item_supplier_pricing_overview
    from frappe.utils import getdate
    merged = {}
    warnings = []
    for row in rows:
        key = row["item_code"]
        if key in merged:
            merged[key]["qty_per_unit"] += row["qty_per_unit"]
            merged[key]["source_refs"] = frappe.as_json(json.loads(merged[key]["source_refs"]) + json.loads(row["source_refs"]))
        else:
            merged[key] = row
    for row in merged.values():
        try:
            overview = get_item_supplier_pricing_overview(row["item_code"])
        except frappe.PermissionError:
            overview = {"rules": {}, "no_permission": True, "supplier_names": {}}
        date = getdate(doc.quotation_date)
        candidates = [r for r in overview["rules"].values() if not r.get("disabled")
                      and (not r.get("company") or r["company"] == doc.company)
                      and (not r.get("valid_from") or getdate(r["valid_from"]) <= date)
                      and (not r.get("valid_upto") or getdate(r["valid_upto"]) >= date)]
        if len(candidates) == 1:
            rule = candidates[0]
            row.update(supplier=rule["supplier"], pricing_rule=rule["name"],
                       price_currency=rule["currency"], minimum_order_qty=rule["minimum_order_qty"],
                       purchase_uom=rule["uom"])
            if rule["uom"] != row["stock_uom"]:
                item = read_source("Item", row["item_code"])
                row["conversion_factor"] = next((u.conversion_factor for u in item.uoms if u.uom == rule["uom"]), 0)
            if rule["currency"] != doc.currency:
                row["price_exchange_rate"] = 0
        else:
            reason = "无供应商阶梯价读取权限" if overview.get("no_permission") else "无可读有效规则" if not candidates else "有多个供应商规则，请选择"
            warnings.append(f"{row['item_code']}：{reason}")
        warnings.append(f"{row['item_code']}：请确认采购价含税口径和单位")
    return list(merged.values()), warnings


def _project_investments(name, doc):
    from client_akivision.utils.project_permissions import require_project_finance
    require_project_finance()
    project = read_source("Project", name, doc.company)
    for field in ("custom_project_cost_details", "custom_project_budget_details"):
        if project.meta.has_field(field) and not project.has_permlevel_access_to(field):
            frappe.throw("缺少项目成本/预算字段权限", frappe.PermissionError)
    fx = flt(doc.exchange_rate)
    rows = []
    for cost in project.get("custom_project_cost_details") or []:
        rows.append({"project": name, "expense_type": cost.cost_type + "：" + cost.expense_description,
                     "actual_amount": flt(cost.amount) * fx, "allocation_percent": 0,
                     "recovery_method": "Amortize", "source_key": f"Project:{cost.name}",
                     "source_refs": _refs("Project", name, cost.name)})
    for budget in project.get("custom_project_budget_details") or []:
        rows.append({"project": name, "expense_type": "预算参考：" + budget.expense_category,
                     "budget_reference": flt(budget.amount) * fx, "allocation_percent": 0,
                     "recovery_method": "Amortize", "source_key": f"Budget:{budget.name}",
                     "source_refs": _refs("Project", name, budget.name)})
    # Project's total_costing_amount already includes all submitted Timesheet
    # Detail rows; read only the underlying rows here to avoid adding the parent
    # total again. Project-finance permission has been checked above. Standard
    # Timesheet Detail has no allocation field; where an install adds one,
    # apply it, otherwise the row is fully allocated to its Project link.
    if not frappe.has_permission("Timesheet", "read"):
        frappe.throw("需要 Timesheet 读取权限，才能完整归集项目实际工时成本", frappe.PermissionError)
    for timesheet_name in frappe.get_list("Timesheet", filters={"docstatus": 1, "company": doc.company}, pluck="name", limit_page_length=0):
        timesheet = read_source("Timesheet", timesheet_name, doc.company)
        for time in timesheet.time_logs:
            if time.project != name:
                continue
            allocation = flt(time.get("allocation_percent"), 100) / 100
            if not allocation:
                allocation = 1
            rows.append({"project": name, "expense_type": "研发工时：" + (time.activity_type or "工时"),
                         "actual_amount": flt(time.base_costing_amount) * allocation * fx, "allocation_percent": 0,
                         "recovery_method": "Amortize", "source_key": f"Timesheet:{time.name}",
                         "source_refs": _refs("Timesheet", timesheet_name, time.name)})
    return rows


def work_order_reference(name, company):
    order = read_source("Work Order", name, company)
    entries, material = [], 0
    consumption_entries = frappe.get_list("Stock Entry", filters={"work_order": name, "docstatus": 1,
                                                                    "purpose": "Material Consumption for Manufacture"},
                                          pluck="name", limit_page_length=0)
    # Prefer the dedicated consumption voucher when present; a later
    # Manufacture voucher can reference the same components and must not add
    # them again as a second material issue.
    entry_names = consumption_entries or frappe.get_list("Stock Entry", filters={
        "work_order": name, "docstatus": 1, "purpose": "Manufacture"}, pluck="name", limit_page_length=0)
    for entry_name in entry_names:
        entry = read_source("Stock Entry", entry_name, company)
        # Transfers into WIP and finished-good output valuation are not consumption.
        amount = sum(
            flt(i.basic_amount)
            for i in entry.get("items") or []
            if i.s_warehouse
            and not i.is_finished_item
            and not i.get("is_scrap_item")
            and not i.get("is_legacy_scrap_item")
            and not i.get("type")
        )
        if entry.is_return:
            amount = -amount
        material += amount
        entries.append({"stock_entry": entry_name, "purpose": entry.purpose, "consumption_amount": amount})
    return {"work_order": name, "status": order.status, "produced_qty": order.produced_qty,
            "planned_qty": order.qty, "actual_material_reference": material,
            "actual_labor_hours": order.get("custom_actual_labor_hours"),
            "actual_labor_cost": order.get("custom_actual_labor_cost"),
            "actual_operating_cost": order.get("actual_operating_cost"),
            "currency": frappe.get_cached_value("Company", company, "default_currency"),
            "entries": entries, "complete": False,
            "note": "历史参考，不计入未来报价。仅统计当前可读的生产耗用凭证；未自动认定凭证齐全。operating_cost可能已包含自定义人工，不再累加。"}


def build_sources(doc):
    require_cost_user()
    result = {"materials": [], "operations": [], "investments": [], "source_warnings": "",
              "actual_reference_json": "", "source_refreshed_at": str(now_datetime())}
    warnings = []
    bom_name = doc.bom_no
    if doc.reference_work_order:
        order = read_source("Work Order", doc.reference_work_order, doc.company)
        if doc.item_code and doc.item_code != order.production_item:
            frappe.throw("生产工单产品不一致")
        bom_name = bom_name or order.bom_no
        result["actual_reference_json"] = frappe.as_json(work_order_reference(order.name, doc.company))
    if bom_name:
        bom = read_source("BOM", bom_name, doc.company)
        if doc.item_code and bom.item != doc.item_code:
            frappe.throw("BOM与产品不一致")
        rows, operations = _expand_bom(bom_name, doc.company)
        result["materials"], price_warnings = _material_defaults(rows, doc)
        result["operations"] = operations
        for row in operations:
            row["hourly_rate"] *= flt(doc.exchange_rate)
        warnings.extend(price_warnings)
    else:
        warnings.append("无BOM：请填写临时材料、制造工时及估算依据")
    projects = {r.project for r in doc.get("investments") or [] if r.project}
    if doc.project:
        projects.add(doc.project)
    for project in sorted(projects):
        result["investments"].extend(_project_investments(project, doc))
        warnings.append(f"项目{project}：实际费用与预算分开；分摊比例默认0，剩余投入、已回收金额须确认；请核对不同来源是否重复")
    result["source_warnings"] = "\n".join(warnings)
    return result


def source_context(source_type="Direct", source_name=None, item_code=None):
    require_cost_user()
    frappe.has_permission("Product Cost Quotation", "create", throw=True)
    if source_type not in ("Direct", "Item", "Project", "Work Order"):
        frappe.throw("不支持的来源类型")
    context = {"source_type": source_type, "item_code": item_code}
    if source_type != "Direct":
        source = read_source(source_type, source_name)
        if source_type == "Item":
            context.update(item_code=source.name, product_name=source.item_name,
                           bom_no=_default_bom(source.name))
        elif source_type == "Project":
            context.update(project=source.name, company=source.company)
        else:
            context.update(reference_work_order=source.name, item_code=source.production_item,
                           company=source.company, bom_no=source.bom_no)
    if context.get("item_code"):
        item = read_source("Item", context["item_code"])
        context.setdefault("product_name", item.item_name)
        context.setdefault("bom_no", _default_bom(item.name))
    company = context.get("company") or frappe.defaults.get_user_default("Company")
    if company:
        read_source("Company", company)
        context.update(company=company, currency=frappe.get_cached_value("Company", company, "default_currency"), exchange_rate=1)
    return context


def _default_bom(item_code):
    bom = frappe.get_list("BOM", filters={"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
                          fields=["name"], limit_page_length=1)
    if bom:
        return bom[0].name
    variant_of = frappe.get_cached_value("Item", item_code, "variant_of")
    if variant_of:
        bom = frappe.get_list("BOM", filters={"item": variant_of, "is_active": 1, "is_default": 1, "docstatus": 1},
                              fields=["name"], limit_page_length=1)
        return bom[0].name if bom else None
    return None
