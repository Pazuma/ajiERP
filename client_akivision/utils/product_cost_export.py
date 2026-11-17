"""Styled, value-only XLSX export. Customer files never contain cost cells."""
from copy import copy
from io import BytesIO
import json
from pathlib import Path

import frappe
from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter


LEFT_LABELS = {"A4": "客户名称：", "A5": "客户联系人：", "A6": "报价单号：", "G5": "报价日期：",
               "G6": "联系电话：", "A7": "报价单", "A9": "类别", "B9": "序号", "C9": "产品名称",
               "D9": "产品型号", "E9": "单位", "F9": "批次含税单价", "K9": "备注"}
RIGHT_LABELS = {"M1": "产品型号", "N1": "已发生研发投入", "O1": "剩余预计投入", "P1": "已回收金额",
                "Q1": "本次单独收费", "R1": "本产品投入", "S1": "核算版本", "T1": "税率", "U1": "币种", "V1": "报价单号",
                "M4": "批量", "M11": "批量", "M12": "定价方式", "M13": "消耗材料成本", "M14": "承担余量及损耗",
                "M15": "总材料成本", "M16": "组装工时(小时/台)", "M17": "组装成本", "M18": "其他工时(小时/台)",
                "M19": "其他制造成本", "M20": "材料及制造成本", "M21": "研发分摊成本", "M22": "完整成本",
                "M23": "建议含税价(含研发)", "M24": "最终报价毛利率", "M25": "批次毛利", "M26": "最终报价回本数量",
                "M27": "建议含税价(不含研发)", "M28": "最终含税报价", "M29": "采购投入", "M30": "采购余量金额"}


def build_template():
    """Generate a controlled asset from styles only, never copying sample values."""
    path = Path(frappe.get_app_path("client_akivision", "templates", "xlsx", "product_cost_quotation.xlsx"))
    if path.exists():
        return str(path)
    source = load_workbook(Path(frappe.get_app_path("client_akivision")).parent / "docs" / "模板.xlsx", keep_links=False)
    target = Workbook()
    _copy_styles(source.active, target.active, 24)
    target.active.title = "成本报价模板"
    for address, value in {**LEFT_LABELS, **RIGHT_LABELS}.items():
        target.active[address] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    target.save(path)
    return str(path)


def _copy_styles(source, target, max_col):
    for row in source.iter_rows(min_row=1, max_row=45, max_col=max_col):
        for cell in row:
            if not isinstance(cell, MergedCell):
                out = target.cell(cell.row, cell.column)
                out.font = copy(cell.font)
                out.fill = copy(cell.fill)
                out.border = copy(cell.border)
                out.protection = copy(cell.protection)
                out.number_format = cell.number_format
                out.alignment = copy(cell.alignment)
    for key, dim in source.column_dimensions.items():
        if dim.min is None or dim.min <= max_col:
            target.column_dimensions[key] = _dimension(dim, target)
    for key, dim in source.row_dimensions.items():
        target.row_dimensions[key] = _dimension(dim, target)
    for merged in source.merged_cells.ranges:
        if merged.max_col <= max_col:
            target.merge_cells(str(merged))
    target.sheet_view.showGridLines = False
    target.sheet_properties.pageSetUpPr.fitToPage = True
    target.page_setup.orientation = "landscape" if max_col > 11 else "portrait"
    target.page_setup.paperSize = target.PAPERSIZE_A4
    target.page_setup.fitToWidth = 1
    target.page_setup.fitToHeight = 1
    target.print_options.horizontalCentered = True
    target.print_area = f"A1:{get_column_letter(max_col)}30"


def _dimension(dim, target):
    result = copy(dim)
    result.parent = target
    result._style = None
    result.font = copy(dim.font)
    result.fill = copy(dim.fill)
    result.border = copy(dim.border)
    result.alignment = copy(dim.alignment)
    result.number_format = dim.number_format
    result.protection = copy(dim.protection)
    return result


def _put(sheet, cell, value):
    out = sheet[cell] if isinstance(cell, str) else sheet.cell(*cell)
    out.value = value
    if isinstance(value, str):
        out.data_type = "s"  # customer names/terms must never become Excel formulas


def export_workbook(doc, audience):
    if audience not in ("internal", "customer"):
        raise ValueError("Invalid audience")
    template = load_workbook(frappe.get_app_path("client_akivision", "templates", "xlsx", "product_cost_quotation.xlsx"), keep_links=False).active
    workbook = Workbook()
    workbook.remove(workbook.active)
    scenarios = list(doc.scenarios)
    if audience == "customer":
        scenarios = [row for row in scenarios if row.get("show_in_customer_quote") is None or row.show_in_customer_quote]
        if not scenarios:
            frappe.throw("请至少选择一个客户报价展示阶梯")
    for page, start in enumerate(range(0, max(len(scenarios), 1), 4), 1):
        sheet = workbook.create_sheet(f"报价单{page}")
        _copy_styles(template, sheet, 24 if audience == "internal" and page == 1 else 11)
        _prepare_left_capacity(sheet)
        for cell, value in LEFT_LABELS.items():
            _put(sheet, cell, value)
        company_name = frappe.get_cached_value("Company", doc.company, "company_name") or doc.company
        contact_name = frappe.get_cached_value("Contact", doc.contact, "full_name") if doc.contact else ""
        customer_name = frappe.get_cached_value("Customer", doc.customer, "customer_name") if doc.customer else ""
        values = {"A1": company_name, "A4": "客户名称：" + (customer_name or ""), "A5": "客户联系人：" + (contact_name or ""),
                  "A6": "报价单号：" + doc.name, "H5": str(doc.quotation_date), "H6": doc.contact_phone or "",
                  "K6": f"第{page}页", "F9": f"批次单价（{doc.currency}，含税{doc.tax_rate:g}%）", "F11": "批量",
                  "A12": "产品", "B12": 1, "C12": doc.product_name, "D12": doc.item_code or doc.provisional_model,
                  "E12": (frappe.get_cached_value("Item", doc.item_code, "stock_uom") if doc.item_code else "PCS") or "PCS", "A20": "报价有效期：" + str(doc.valid_until or "未设置"),
                  "A21": doc.terms or "", "A23": "请确认后回传。",
                  "A24": "我方联系人：" + (doc.get("sales_contact") or ""),
                  "A25": "我方联系电话：" + (doc.get("sales_phone") or "")}
        separate = sum(float(r.separate_charge or 0) for r in doc.investments)
        if separate:
            values["K12"] = f"另收一次性费用(未税)：{separate:g} {doc.currency}"
        if doc.docstatus == 0:
            values["A7"] = "报价单（草稿 / 未确认，不可作为正式报价）"
            values["A22"] = "数据状态：" + ("不完整" if any(r.completeness == "Incomplete" for r in scenarios) else "待确认")
        for cell, value in values.items():
            _put(sheet, cell, value)
        for index, row in enumerate(scenarios[start:start + 4]):
            _put(sheet, (11, 7 + index), row.quantity)
            _put(sheet, (12, 7 + index), row.final_tax_inclusive_price)
        if audience == "internal" and page == 1:
            _internal(sheet, doc)
    if audience == "internal":
        _details(workbook, doc)
    workbook.calculation.fullCalcOnLoad = False
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _prepare_left_capacity(sheet):
    # The source workbook merged I:J, which leaves only three quantity slots.
    # Split that final merged quote cell so all four 50/100/200/500 scenarios
    # fit on the customer-facing page without dropping a batch.
    for merged in ("I11:J11", "I12:J12"):
        if merged in {str(rng) for rng in sheet.merged_cells.ranges}:
            sheet.unmerge_cells(merged)
    for row in (9, 10, 11):
        sheet.cell(row, 10)._style = copy(sheet.cell(9, 9)._style)
    sheet.cell(12, 10)._style = copy(sheet.cell(12, 9)._style)


def _internal(sheet, doc):
    for cell, value in RIGHT_LABELS.items():
        _put(sheet, cell, value)
    for cell, value in {"M2": doc.item_code or doc.provisional_model, "N2": sum(r.actual_amount or 0 for r in doc.investments),
                        "O2": sum(r.remaining_estimate or 0 for r in doc.investments), "P2": sum(r.recovered_amount or 0 for r in doc.investments),
                        "Q2": sum(r.separate_charge or 0 for r in doc.investments),
                        "R2": sum((r.actual_amount + r.remaining_estimate) * r.allocation_percent / 100 for r in doc.investments),
                        "S2": doc.calculation_version, "T2": doc.tax_rate / 100, "U2": doc.currency, "V2": doc.name}.items():
        _put(sheet, cell, value)
    categories = sorted({r.category or "其他材料" for r in doc.materials})
    for i, label in enumerate(categories[:4] + (["其他类别合计"] if len(categories) > 4 else []), 5):
        _put(sheet, (i, 13), label)
    for col, row in enumerate(doc.scenarios, 14):
        if col > 24:
            sheet.column_dimensions[get_column_letter(col)].width = sheet.column_dimensions["X"].width or 14
            for r in range(1, 31):
                sheet.cell(r, col)._style = copy(sheet.cell(r, 24)._style)
        details = json.loads(row.detail_snapshot_json or "{}")
        qty = row.quantity
        consume = sum(d.get("consumed_cost", 0) for d in details.get("materials", [])) / qty
        for i, category in enumerate(categories[:4], 5):
            _put(sheet, (i, col), sum(d.get("charged_cost", 0) for d in details.get("materials", []) if d.get("category") == category) / qty)
        if len(categories) > 4:
            _put(sheet, (9, col), sum(d.get("charged_cost", 0) for d in details.get("materials", []) if d.get("category") in categories[4:]) / qty)
        mapping = {4: qty, 11: qty, 12: doc.pricing_method, 13: consume,
                   14: row.material_unit_cost - consume, 15: row.material_unit_cost,
                   20: row.material_unit_cost + row.manufacturing_unit_cost, 21: row.investment_unit_cost,
                   22: row.full_unit_cost, 23: row.suggested_price_with_rd, 24: row.gross_margin / 100,
                   25: row.batch_gross_profit, 26: row.payback_qty if row.payback_qty else "无需回收/无法回本，见风险提示",
                   27: row.suggested_price_without_rd, 28: row.final_tax_inclusive_price,
                   29: row.procurement_total, 30: row.surplus_total}
        assembly = [(op, value) for op, value in zip(doc.operations, details.get("operations", [])) if "组装" in op.operation or "装配" in op.operation]
        assembly_cost = sum(v["cost"] for _, v in assembly) / qty
        assembly_hours = sum(v["hours"] * (1 if op.charging_basis == "Per Unit" else 1 / qty) for op, v in assembly)
        total_hours = sum(v["hours"] * (1 if op.charging_basis == "Per Unit" else 1 / qty) for op, v in zip(doc.operations, details.get("operations", [])))
        mapping.update({16: assembly_hours, 17: assembly_cost, 18: total_hours - assembly_hours, 19: row.manufacturing_unit_cost - assembly_cost})
        for r, value in mapping.items():
            _put(sheet, (r, col), value)
    sheet.print_area = f"A1:{get_column_letter(max(24, 13 + len(doc.scenarios)))}30"


def _details(workbook, doc):
    for title, table in (("物料阶梯明细", "materials"), ("制造工时", "operations"), ("项目投入及来源", "investments")):
        sheet = workbook.create_sheet(title)
        rows = doc.get(table) or []
        fields = [f for f in frappe.get_meta(rows[0].doctype).fields if f.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML")] if rows else []
        for col, field in enumerate(fields, 1):
            _put(sheet, (1, col), field.label)
            sheet.column_dimensions[get_column_letter(col)].width = 22
        for index, row in enumerate(rows, 2):
            for col, field in enumerate(fields, 1):
                value = row.get(field.fieldname)
                if field.fieldname in ("source_refs", "calculation_details_json", "tier_overrides_json") and value:
                    try:
                        value = json.dumps(json.loads(value), ensure_ascii=False, indent=2)
                    except (ValueError, TypeError):
                        pass
                _put(sheet, (index, col), value)
    evidence = workbook.create_sheet("快照与风险")
    for index, (key, value) in enumerate([("单号", doc.name), ("快照校验", doc.snapshot_hash),
                                          ("来源提示", doc.source_warnings), ("工单实际参考", doc.actual_reference_json)] +
                                         [(f"批量{r.quantity:g}", r.warnings or "完整") for r in doc.scenarios], 1):
        _put(evidence, (index, 1), key)
        _put(evidence, (index, 2), value)
