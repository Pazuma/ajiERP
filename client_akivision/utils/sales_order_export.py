"""Read-only, audience-specific sales order exports."""
from io import BytesIO

import frappe
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from client_akivision.utils.formal_pdf_export import read_doc, render_pdf

COST_ROWS = (
    (("订单损耗率 (%)", "custom_order_loss_rate"), ("按订单归集生产成本", "custom_enable_production_cost"), ("", "")),
    (("实际材料成本", "custom_material_cost"), ("辅助材料成本", "custom_auxiliary_material_cost"), ("人工成本", "custom_labor_cost")),
    (("制造费用", "custom_manufacturing_overhead"), ("正常损耗成本", "custom_normal_loss_cost"), ("异常损耗成本", "custom_abnormal_loss_cost")),
    (("废料回收价值", "custom_scrap_recovery"), ("生产总成本", "custom_production_cost"), ("已发货销售成本", "custom_delivered_cost")),
    (("已确认收入", "custom_recognized_revenue"), ("订单毛利", "custom_gross_profit"), ("订单毛利率 (%)", "custom_gross_margin")),
)


def customer_context(doc):
    # Explicit allow-list: never pass the Sales Order document to customer templates.
    included = [bool(t.included_in_print_rate) for t in doc.taxes if t.charge_type != "Actual"]
    basis = "含税" if included and all(included) else "未税" if not any(included) else "订单口径"
    return dict(company=doc.company, name=doc.name, date=str(doc.transaction_date),
                status={0: "草稿", 1: "已提交", 2: "已取消"}[doc.docstatus],
                customer=doc.customer_name or doc.customer, contact=doc.get("contact_display") or "",
                phone=doc.get("contact_mobile") or doc.get("contact_phone") or "",
                address=frappe.utils.strip_html(doc.get("shipping_address") or ""),
                currency=doc.currency, basis=basis,
                items=[dict(code=r.item_code, name=r.item_name, model=r.get("custom_model") or "",
                            qty=r.qty, uom=r.uom, rate=r.rate, amount=r.amount, date=str(r.delivery_date or "")) for r in doc.items],
                taxes=[dict(label=t.description, rate=t.rate, amount=t.tax_amount) for t in doc.taxes],
                qty=doc.total_qty, net=doc.net_total, tax=doc.total_taxes_and_charges,
                discount=doc.discount_amount, rounding=doc.rounding_adjustment,
                total=doc.rounded_total or doc.grand_total, words=doc.in_words,
                terms=frappe.utils.strip_html(doc.get("terms") or ""),
                payment=doc.get("payment_terms_template") or "按订单约定")


def append_safe(ws, values):
    ws.append(values)
    for cell in ws[ws.max_row]:
        if isinstance(cell.value, str):
            cell.data_type = "s"


def workbook(doc, context, internal=False):
    wb = Workbook()
    ws = wb.active
    ws.title = "订单明细"
    for values in ([context["company"]], ["销售订单 · " + context["status"]],
                   ["订单编号", context["name"], "订单日期", context["date"]],
                   ["客户", context["customer"], "联系人", context["contact"]],
                   ["联系电话", context["phone"], "币种", context["currency"]],
                   ["收货地址", context["address"]], [],
                   ["序号", "产品编码", "产品名称", "型号", "数量", "单位", context["basis"] + "单价", context["basis"] + "金额", "交货日期"]):
        append_safe(ws, values)
    for i, r in enumerate(context["items"], 1):
        append_safe(ws, [i, r["code"], r["name"], r["model"], r["qty"], r["uom"], r["rate"], r["amount"], r["date"]])
    for label, value in (("合计数量", context["qty"]), ("未税金额", context["net"]),
                         ("税费合计", context["tax"]), ("折扣", context["discount"]),
                         ("舍入调整", context["rounding"]), ("订单合计", context["total"]),
                         ("大写金额", context["words"]), ("付款方式", context["payment"]), ("条款", context["terms"])):
        append_safe(ws, [label, value])
    for tax in context["taxes"]:
        append_safe(ws, ["税费明细", tax["label"], tax["rate"], tax["amount"]])
    append_safe(ws, ["制单人：________", "公司确认：________", "客户确认：________"])
    ws.merge_cells("A1:I1")
    ws.merge_cells("A2:I2")
    logo = frappe.get_app_path("client_akivision", "public", "images", "aki_vision_logo.png")
    from pathlib import Path
    if Path(logo).is_file():
        image = Image(logo)
        image.width, image.height = 100, 36
        ws.add_image(image, "I1")
        ws.row_dimensions[1].height = 30
    if internal:
        cost = wb.create_sheet("成本与毛利")
        append_safe(cost, ["销售订单成本与毛利", doc.name, doc.company])
        append_safe(cost, ["成本币种", doc.get("company_currency") or frappe.get_cached_value("Company", doc.company, "default_currency")])
        append_safe(cost, ["成本更新时间", str(doc.get("custom_cost_last_updated") or "尚未归集")])
        for row in COST_ROWS:
            append_safe(cost, [cell[0] for cell in row])
            append_safe(cost, [doc.get(cell[1]) if cell[1] else "" for cell in row])
        append_safe(cost, ["说明：采用已有归集结果，不触发重算；未归集或部分履约时不代表最终毛利。"])
        source = wb.create_sheet("来源记录")
        append_safe(source, ["单据类型", "单据编号", "关联说明"])
        if doc.get("project") and frappe.has_permission("Project", "read", doc=frappe.get_doc("Project", doc.project)):
            append_safe(source, ["项目", doc.project, "订单关联项目"])
        for dt, filters, note in (
            ("Work Order", {"sales_order": doc.name}, "关联生产工单"),
            ("Stock Entry", {"custom_sales_order": doc.name}, "关联库存记录"),
            ("Delivery Note Item", {"against_sales_order": doc.name}, "关联销售送货单"),
        ):
            if not frappe.has_permission("Delivery Note" if dt == "Delivery Note Item" else dt, "read"):
                continue
            rows = frappe.get_list(dt, filters=filters, fields=["parent" if dt == "Delivery Note Item" else "name"],
                                   parent_doctype="Delivery Note" if dt == "Delivery Note Item" else None, limit_page_length=0)
            for name in sorted({r.get("parent") or r.name for r in rows}):
                parent_dt = "Delivery Note" if dt == "Delivery Note Item" else dt
                if not frappe.has_permission(parent_dt, "read", doc=frappe.get_doc(parent_dt, name)):
                    continue
                append_safe(source, ["销售送货单" if dt == "Delivery Note Item" else "生产工单" if dt == "Work Order" else "库存凭证", name, note])
    for sheet in wb:
        sheet.freeze_panes = "A9" if sheet == ws else "A2"
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_options.horizontalCentered = True
        sheet.oddFooter.center.text = "第 &P 页 / 共 &N 页"
        sheet.print_title_rows = "1:8" if sheet == ws else "1:1"
        for col in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 24
        for row in sheet:
            for cell in row:
                cell.alignment = Alignment(vertical="center", wrap_text=True, horizontal="right" if isinstance(cell.value, (int, float)) else "left")
                if isinstance(cell.value, (int, float)):
                    cell.number_format = "#,##0.00"
                if cell.row in (1, 2) or (sheet == ws and cell.row == 8):
                    cell.fill = PatternFill("solid", fgColor="24415C")
                    cell.font = Font(color="FFFFFF", bold=True)
        sheet.print_area = sheet.dimensions
    result = BytesIO()
    wb.save(result)
    return result.getvalue()


@frappe.whitelist()
def download_sales_order(name, audience="customer", file_type="xlsx"):
    if audience not in ("customer", "internal") or file_type not in ("xlsx", "pdf") or (audience == "internal" and file_type != "xlsx"):
        frappe.throw("不支持的导出类型")
    doc = read_doc("Sales Order", name)
    doc.check_permission("export" if file_type == "xlsx" else "print")
    if audience == "internal":
        if not {"System Manager", "Accounts Manager", "Accounts User", "China Finance User", "China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor"}.intersection(frappe.get_roles()):
            frappe.throw("仅财务和管理员可导出内部成本", frappe.PermissionError)
        for row in COST_ROWS:
            for _, field in row:
                if field and doc.meta.has_field(field) and not doc.has_permlevel_access_to(field):
                    frappe.throw("缺少成本字段读取权限", frappe.PermissionError)
    context = customer_context(doc)
    data = workbook(doc, context, audience == "internal") if file_type == "xlsx" else render_pdf(
        "templates/sales_order_customer_export.html", context, "Landscape")
    frappe.local.response.filename = f"{doc.name}-{'内部核算' if audience == 'internal' else '客户订单'}.{file_type}"
    frappe.local.response.filecontent = data
    frappe.local.response.type = "download"
