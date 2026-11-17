"""New APIs only; existing quotation, pricing and actual-cost APIs are unchanged."""
import json

import frappe
from frappe.utils import cstr

from client_akivision.utils.product_cost_permissions import APPROVERS, require_cost_user, check_sources
from client_akivision.utils.product_cost_sources import source_context, build_sources


def _document(name, write=False, expected_modified=None):
    require_cost_user()
    doc = frappe.get_doc("Product Cost Quotation", name)
    doc.check_permission("write" if write else "read")
    if expected_modified is not None and cstr(doc.modified) != cstr(expected_modified):
        frappe.throw("单据已被其他用户修改，请刷新后重试", frappe.TimestampMismatchError)
    if write and doc.docstatus != 0:
        frappe.throw("仅草稿允许刷新或重新核算，请复制新版本")
    check_sources(doc)
    return doc


@frappe.whitelist()
def get_source_context(source_type="Direct", source_name=None, item_code=None):
    return source_context(source_type, source_name, item_code)


@frappe.whitelist()
def set_default_product_quote(name):
    """Bind a submitted costing quote to its Item without exposing costing rows."""
    if not APPROVERS.intersection(frappe.get_roles()):
        frappe.throw("只有系统管理员或财务经理可以设定产品默认成本报价。", frappe.PermissionError)
    doc = _document(name)
    if doc.docstatus != 1:
        frappe.throw("只有已确认的成本报价单才能设为产品默认报价。")
    if not doc.item_code:
        frappe.throw("成本报价单尚未关联产品。")
    item = frappe.get_doc("Item", doc.item_code)
    project = item.get("custom_development_project")
    if project and doc.project and project != doc.project:
        frappe.throw("报价单主项目与产品关联项目不一致，请先核对项目归属。")
    values = {"custom_default_cost_quotation": doc.name}
    if doc.project and not project:
        values["custom_development_project"] = doc.project
    item.db_set(values, update_modified=True)
    frappe.clear_document_cache("Item", item.name)
    return {"item_code": item.name, "quotation": doc.name, "project": values.get("custom_development_project", project)}


@frappe.whitelist()
def get_sales_order_quote_options(item_code, company, currency):
    """Return only customer-facing prices for the selected Item's default quote."""
    frappe.has_permission("Item", "read", doc=item_code, throw=True)
    default_quote = frappe.db.get_value("Item", item_code, "custom_default_cost_quotation")
    if not default_quote:
        return None
    quote = frappe.get_doc("Product Cost Quotation", default_quote)
    if quote.docstatus != 1 or quote.item_code != item_code:
        frappe.throw("产品默认成本报价单未确认或产品不匹配，请联系成本核算人员。")
    if quote.company != company or quote.currency != currency:
        return {"quotation": quote.name, "compatible": False,
                "reason": "报价单公司或币种与销售订单不一致，未自动应用报价。"}
    return {
        "quotation": quote.name,
        "item_code": item_code,
        "compatible": True,
        "currency": quote.currency,
        "project": frappe.db.get_value("Item", item_code, "custom_development_project") or quote.project,
        "scenarios": [
            {"quantity": row.quantity, "price": row.final_tax_inclusive_price}
            for row in quote.scenarios
            if row.show_in_customer_quote and row.final_tax_inclusive_price
        ],
    }


@frappe.whitelist()
def get_sales_order_cost_quote_snapshots(sales_order):
    from client_akivision.utils.sales_order_product_cost import get_order_quote_snapshots
    return get_order_quote_snapshots(sales_order)


@frappe.whitelist()
def get_material_pricing_options(item_code):
    require_cost_user()
    frappe.has_permission("Product Cost Quotation", "create", throw=True)
    from custom_filters.item_supplier_pricing import get_item_supplier_pricing_overview
    return get_item_supplier_pricing_overview(item_code)


@frappe.whitelist()
def preview_source_refresh(name):
    doc = _document(name, write=True)
    source = build_sources(doc)
    diffs = {}
    for key in ("materials", "operations", "investments"):
        old = {r.source_key: r.as_dict() for r in doc.get(key) or [] if r.source_key}
        new = {r["source_key"]: r for r in source[key]}
        fields = [f.fieldname for f in frappe.get_meta(doc.meta.get_field(key).options).fields
                  if f.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML")
                  and f.fieldname not in ("source_refs", "source_key", "calculation_details_json")]
        changes = []
        for source_key in sorted(old.keys() | new.keys()):
            before, after = old.get(source_key), new.get(source_key)
            changed = [{"fieldname": field, "before": before.get(field), "after": after.get(field)}
                       for field in fields if before and after and cstr(before.get(field) or "") != cstr(after.get(field) or "")]
            if before and after:
                before_refs = sorted(ref.get("name", "") for ref in frappe.parse_json(before.get("source_refs") or "[]"))
                after_refs = sorted(ref.get("name", "") for ref in frappe.parse_json(after.get("source_refs") or "[]"))
                if before_refs != after_refs:
                    changed.append({"fieldname": "source_refs", "before": ", ".join(before_refs) or "空",
                                    "after": ", ".join(after_refs) or "空"})
            if not before or not after or changed:
                changes.append({"source_key": source_key, "action": "新增" if not before else "移除" if not after else "变更",
                                "changes": changed})
        diffs[key] = changes
    return {"modified": doc.modified, "source": source,
            "diffs": diffs,
            "groups": [{"fieldname": key, "old_count": len(doc.get(key) or []), "new_count": len(source[key]),
                        "has_changes": bool(diffs[key])}
                       for key in ("materials", "operations", "investments")],
            "warning": "仅替换选中的来源明细；无来源键的手工行保留。已有来源行中的手工调整会被替换，请核对后选择。"}


@frappe.whitelist(methods=["POST"])
def apply_source_refresh(name, expected_modified, selected_changes):
    # Row lock plus Frappe save's timestamp check prevents concurrent overwrite.
    frappe.db.sql("select name from `tabProduct Cost Quotation` where name=%s for update", name)
    doc = _document(name, write=True, expected_modified=expected_modified)
    selected = frappe.parse_json(selected_changes)
    if not isinstance(selected, list) or not selected or any(k not in ("materials", "operations", "investments") for k in selected):
        frappe.throw("请选择有效的来源分组")
    source = build_sources(doc)
    for key in selected:
        manual = [r.as_dict() for r in doc.get(key) or [] if not r.source_key]
        doc.set(key, manual + source[key])
    for key in ("source_warnings", "actual_reference_json", "source_refreshed_at"):
        doc.set(key, source[key])
    doc.estimate_acknowledged = 0
    doc.flags.refreshed_source_context = {key: [doc.item_code or None, doc.bom_no or None] for key in selected if key in ("materials", "operations")}
    doc.save()
    return {"name": doc.name, "modified": doc.modified,
            "counts": {key: len(doc.get(key) or []) for key in ("materials", "operations", "investments")}}


@frappe.whitelist()
def preview_calculation(name, expected_modified):
    doc = _document(name, write=True, expected_modified=expected_modified)
    return doc.recalculate()


@frappe.whitelist()
def get_line_detail(name, child_row, scenario_qty=None):
    doc = _document(name)
    for key in ("materials", "operations", "investments", "scenarios"):
        row = next((r for r in doc.get(key) or [] if r.name == child_row), None)
        if row:
            if key == "materials":
                data = json.loads(row.calculation_details_json or "[]")
                if scenario_qty is not None:
                    data = [r for r in data if float(r["quantity"]) == float(scenario_qty)]
                return {"row": row.as_dict(), "calculations": data}
            return {"row": row.as_dict()}
    frappe.throw("明细不属于当前单据", frappe.PermissionError)


@frappe.whitelist()
def export_cost_quotation(name, audience="internal"):
    doc = _document(name)
    doc.check_source_context()
    doc.check_permission("export")
    if audience not in ("internal", "customer"):
        frappe.throw("导出类型无效")
    if doc.docstatus == 2:
        frappe.throw("已取消单据不能作为有效报价导出")
    from client_akivision.utils.product_cost_export import export_workbook
    frappe.local.response.filename = f"{doc.name}-{audience}.xlsx"
    frappe.local.response.filecontent = export_workbook(doc, audience)
    frappe.local.response.type = "binary"
