"""Versioned, value-only XLSX exchange. Source rows are never writable."""
from io import BytesIO
import math
from zipfile import ZipFile

import frappe
from openpyxl import Workbook, load_workbook

VERSION = "PCQ-1"
MAIN = "customer contact contact_phone quotation_date valid_until terms sales_contact sales_phone".split()
SCENARIOS = "quantity final_tax_inclusive_price price_override_reason show_in_customer_quote".split()
TABLES = {
    "scenarios": SCENARIOS,
    "materials": "item_code description category qty_per_unit stock_uom purchase_uom conversion_factor supplier pricing_rule price_basis manual_rate price_currency price_exchange_rate tax_basis purchase_tax_rate minimum_order_qty pack_multiple surplus_policy loss_method loss_rate manual_reason".split(),
    "operations": "operation workstation charging_basis standard_hours hourly_rate included_cost_scope manual_reason".split(),
    "investments": "project expense_type actual_amount remaining_estimate allocation_percent recovered_amount separate_charge recovery_method amortization_qty rd_markup_rate manual_reason".split(),
}
PARAMETERS = "tax_rate minimum_sales_qty pricing_method target_margin cost_ratio".split()


def workbook(doc, kind, empty=False):
    if kind not in ("customer", "internal"):
        frappe.throw("模板类型无效")
    book = Workbook()
    meta = book.active
    meta.title = "说明"
    for row in [("version", VERSION), ("type", kind), ("name", "" if empty else doc.name),
                ("product", doc.item_code or doc.provisional_model), ("company", doc.company),
                ("currency", doc.currency), ("使用说明", "仅值；空格不清空；不删除原行；来源行不可导入。")]:
        meta.append(row)
    fields = MAIN + (PARAMETERS if kind == "internal" else [])
    sheet = book.create_sheet("main")
    sheet.append(fields)
    if not empty:
        sheet.append([doc.get(f) for f in fields])
    for table, fields in TABLES.items():
        if kind == "customer" and table != "scenarios":
            continue
        sheet = book.create_sheet(table)
        sheet.append(["row_id"] + fields)
        if not empty:
            for row in doc.get(table) or []:
                if table != "scenarios" and row.source_key:
                    continue
                sheet.append([row.name] + [row.get(f) for f in fields])
    for sheet in book:
        sheet.freeze_panes = "A2"
        for col in sheet.columns:
            sheet.column_dimensions[col[0].column_letter].width = 24
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    output = BytesIO()
    book.save(output)
    return output.getvalue()


def parse(data, doc):
    if len(data) > 5 * 1024 * 1024:
        frappe.throw("文件不得超过5MB")
    with ZipFile(BytesIO(data)) as archive:
        if sum(info.file_size for info in archive.infolist()) > 25 * 1024 * 1024:
            frappe.throw("文件解压后过大")
        if any("vbaProject" in n or "externalLink" in n for n in archive.namelist()):
            frappe.throw("不接受宏或外链")
    book = load_workbook(BytesIO(data), read_only=True, data_only=False, keep_links=False)
    try:
        if len(book.sheetnames) > 6 or "说明" not in book:
            frappe.throw("不是受控成本报价模板")
        meta = dict((r[0], r[1]) for r in book["说明"].iter_rows(values_only=True) if len(r) >= 2 and r[0])
        if meta.get("version") != VERSION or meta.get("type") not in ("customer", "internal"):
            frappe.throw("模板版本或类型无效")
        for key, value in {"product": doc.item_code or doc.provisional_model, "company": doc.company, "currency": doc.currency}.items():
            if meta.get(key) != value:
                frappe.throw("模板产品、公司或币种与当前单据不一致")
        if meta.get("name") and meta["name"] != doc.name:
            frappe.throw("模板不属于当前报价单")
        kind = meta["type"]
        allowed = {"main": MAIN + (PARAMETERS if kind == "internal" else []), **{
            key: ["row_id"] + fields for key, fields in TABLES.items() if kind == "internal" or key == "scenarios"}}
        changes, errors, seen = [], [], set()
        for sheet in book:
            if sheet.title == "说明":
                continue
            if sheet.title not in allowed:
                errors.append(f"未知工作表：{sheet.title}")
                continue
            rows = sheet.iter_rows()
            headers = [c.value for c in next(rows, [])]
            if not headers or len(headers) != len(set(headers)) or any(h not in allowed[sheet.title] for h in headers):
                errors.append(f"{sheet.title}：表头无效或重复")
                continue
            for idx, cells in enumerate(rows, 2):
                if idx > 2001:
                    frappe.throw("每张工作表最多2000行")
                if not any(c.value is not None for c in cells):
                    continue
                try:
                    if any(c.data_type == "f" for c in cells):
                        raise ValueError("不接受公式，请粘贴为值")
                    values = {key: cell.value for key, cell in zip(headers, cells) if cell.value is not None}
                    row_id = values.pop("row_id", None)
                    group = sheet.title
                    target = doc if group == "main" else next((r for r in doc.get(group) if r.name == row_id), None)
                    if group == "main" and idx != 2:
                        raise ValueError("主单只允许一行")
                    if row_id and not target:
                        raise ValueError("行ID不属于当前单据")
                    if target and group != "main" and target.get("source_key"):
                        raise ValueError("来源行不可通过导入覆盖")
                    if group == "scenarios":
                        qty = float(values.get("quantity") or (target.quantity if target else 0))
                        target = target or next((r for r in doc.scenarios if float(r.quantity) == qty), None)
                        if kind == "customer" and not target:
                            raise ValueError("客户模板只允许更新已有阶梯")
                        if qty <= 0 or not math.isfinite(qty):
                            raise ValueError("批量须为正数")
                        identity = (group, qty)
                    else:
                        identity = (group, target.name if target else f"new-{idx}")
                    if identity in seen:
                        raise ValueError("重复行或重复批量")
                    seen.add(identity)
                    dt = doc.doctype if group == "main" else doc.meta.get_field(group).options
                    for key, value in values.items():
                        field = frappe.get_meta(dt).get_field(key)
                        if field.fieldtype == "Date":
                            from frappe.utils import getdate
                            values[key] = value = getdate(value).isoformat()
                        if field.fieldtype in ("Float", "Currency", "Int", "Check"):
                            value = float(value)
                            if not math.isfinite(value) or value < 0 or (field.fieldtype == "Check" and value not in (0, 1)):
                                raise ValueError(f"{key}数值无效")
                            values[key] = value
                        if field.fieldtype == "Select" and value not in (field.options or "").split("\n"):
                            raise ValueError(f"{key}选项无效")
                        if field.fieldtype == "Link" and value:
                            frappe.get_doc(field.options, value).check_permission("read")
                    delta = {k: v for k, v in values.items() if (target.get(k) if target else None) != v and str(target.get(k) if target else "") != str(v)}
                    if delta:
                        changes.append({"group": group, "line": idx, "row_id": target.name if target else None,
                                        "before": {k: target.get(k) if target else None for k in delta}, "values": delta})
                except (ValueError, TypeError) as exc:
                    errors.append(f"{sheet.title}第{idx}行：{exc}")
        return {"kind": kind, "changes": changes, "errors": errors}
    finally:
        book.close()
