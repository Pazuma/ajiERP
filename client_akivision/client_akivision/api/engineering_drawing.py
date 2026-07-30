import re

import frappe
from frappe import _
from frappe.utils import today
from client_akivision.utils.drawing_service import get_adapter


def get_finalized_drawing(drawing_name):
    drawing = frappe.get_doc("Engineering Drawing", drawing_name)
    if drawing.status != "Finalized":
        frappe.throw(_("只有已定稿图纸才能创建采购或生产单据。"))
    return drawing


@frappe.whitelist()
def drawing_file_action(drawing_name, action="preview"):
	drawing = get_finalized_drawing(drawing_name)
	if action not in {"preview", "download"}:
		frappe.throw(_("不支持的图纸操作。"))
	if not frappe.has_permission("Engineering Drawing", "read"):
		frappe.throw(_("没有查看图纸的权限。"), frappe.PermissionError)
	settings = frappe.get_single("Engineering Drawing Settings")
	if not settings.enable_preview:
		frappe.throw(_("工程图纸预览功能已关闭。"))
	if drawing.file_source not in ("服务器图纸", "客户图纸服务器"):
		if not drawing.drawing_file:
			frappe.throw(_("当前图纸没有本地附件。"))
		if action == "download" and not settings.allow_download:
			frappe.throw(_("本地图纸下载功能已关闭。"))
		return {"source": "local", "url": drawing.drawing_file, "status": "可用"}
	url = get_adapter().signed_url(drawing.external_file_id, frappe.session.user, action)
	if not url:
		return {"source": "external", "status": "不可用", "message": "图纸代理服务尚未配置或外部文件 ID 为空。"}
	return {"source": "external", "url": url, "status": "可用"}


def get_linked_submitted_bom(drawing):
    if not drawing.bom:
        frappe.throw(_("请先在图纸上关联 BOM。"))
    bom = frappe.get_doc("BOM", drawing.bom)
    if bom.docstatus != 1:
        frappe.throw(_("BOM {0} 必须先提交。").format(bom.name))
    if bom.custom_engineering_drawing != drawing.name:
        frappe.throw(_("BOM 必须关联当前已定稿图纸后，才能创建下游单据。"))
    return bom


@frappe.whitelist()
def create_revision(drawing_name):
    source = get_finalized_drawing(drawing_name)
    if not ("Manufacturing User" in frappe.get_roles() or source.can_approve()):
        frappe.throw(_("没有创建图纸修订版的权限。"), frappe.PermissionError)

    revision = next_revision(source.revision)
    drawing = frappe.copy_doc(source)
    drawing.status = "Draft"
    drawing.revision = revision
    drawing.drawing_no = next_drawing_no(source.drawing_no, revision)
    drawing.previous_revision = source.name
    drawing.approved_by = None
    drawing.approved_on = None
    drawing.insert()
    return drawing.name


@frappe.whitelist()
def link_finalized_references(drawing_name, item=None, bom=None):
    """Allow only missing references to be completed after drawing finalization."""
    drawing = get_finalized_drawing(drawing_name)
    if not ("Manufacturing User" in frappe.get_roles() or drawing.can_approve()):
        frappe.throw(_("没有补充图纸关联信息的权限。"), frappe.PermissionError)
    if not item and not bom:
        frappe.throw(_("请至少选择一个待关联的物料或 BOM。"))

    _set_missing_reference(drawing, "item", item, _("关联物料"))
    _set_missing_reference(drawing, "bom", bom, _("关联BOM"))

    if bom:
        bom_doc = frappe.get_doc("BOM", bom)
        if bom_doc.docstatus == 1 and bom_doc.custom_engineering_drawing != drawing.name:
            frappe.throw(_("已提交 BOM 必须先在 BOM 表头关联当前图纸，才能回填到图纸。"))

    drawing.save()
    return drawing.name


def _set_missing_reference(drawing, fieldname, value, label):
    if not value:
        return
    current_value = drawing.get(fieldname)
    if current_value and current_value != value:
        frappe.throw(_("{0} 已关联为 {1}，不能替换已定稿图纸的关联。").format(label, current_value))
    if not current_value:
        drawing.set(fieldname, value)


@frappe.whitelist()
def get_material_request_draft(drawing_name):
    """Build, but do not save, a purchase Material Request for a finalized drawing."""
    drawing = get_finalized_drawing(drawing_name)
    if not frappe.has_permission("Material Request", "create"):
        frappe.throw(_("没有创建采购物料请购的权限。"), frappe.PermissionError)
    bom = get_linked_submitted_bom(drawing)

    request = frappe.new_doc("Material Request")
    request.material_request_type = "Purchase"
    request.company = bom.company
    request.custom_engineering_drawing = drawing.name
    request.custom_engineering_drawing_no = drawing.drawing_no
    request.custom_engineering_drawing_revision = drawing.revision
    for item in bom.items:
        if not item.item_code or not item.qty:
            continue
        request.append(
            "items",
            {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom or item.stock_uom,
                "schedule_date": today(),
                "bom_no": bom.name,
            },
        )
    if not request.items:
        frappe.throw(_("关联 BOM 没有可请购的物料。"))

    # A warehouse is mandatory only when the Material Request is saved. Return a
    # local document so the user can choose the appropriate warehouse per row first.
    return request.as_dict()


@frappe.whitelist()
def create_work_order(drawing_name):
    drawing = get_finalized_drawing(drawing_name)
    if not frappe.has_permission("Work Order", "create"):
        frappe.throw(_("没有创建生产工单的权限。"), frappe.PermissionError)
    bom = get_linked_submitted_bom(drawing)

    existing = frappe.db.get_value(
        "Work Order",
        {"custom_engineering_drawing": drawing.name, "docstatus": ["<", 2]},
        "name",
    )
    if existing:
        return existing

    from erpnext.manufacturing.doctype.work_order.work_order import make_work_order

    work_order = make_work_order(bom.name, bom.item, bom.quantity, company=bom.company)
    work_order.custom_engineering_drawing = drawing.name
    work_order.custom_engineering_drawing_no = drawing.drawing_no
    work_order.custom_engineering_drawing_revision = drawing.revision
    work_order.insert()
    return work_order.name


def next_revision(revision):
    revision = (revision or "v0").strip()
    if match := re.fullmatch(r"[vV](\d+)", revision):
        return f"v{int(match.group(1)) + 1}"
    if revision.isdigit():
        return str(int(revision) + 1)
    if re.fullmatch(r"[A-Z]", revision):
        return chr(ord(revision) + 1) if revision != "Z" else "AA"
    if re.fullmatch(r"[A-Z]+", revision):
        return f"{revision}-1"
    return f"{revision}-1"


def next_drawing_no(drawing_no, revision):
    """Keep the company drawing-number convention (e.g. 1025101100-v0 → -v1)."""
    drawing_no = (drawing_no or "").strip()
    if re.search(r"-[vV]\d+$", drawing_no):
        return re.sub(r"-[vV]\d+$", f"-{revision}", drawing_no)
    return f"{drawing_no}-{revision}" if drawing_no else revision
