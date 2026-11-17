"""Additive BOM revisions: immutable submitted sources, explicit activation."""
import frappe
from frappe.utils import cint
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_schema():
    create_custom_fields({"BOM": [
        dict(fieldname="custom_first_activated_at", label="首次启用时间", fieldtype="Datetime", insert_after="custom_version_no", read_only=1, no_copy=1),
        dict(fieldname="custom_version_source", label="来源版本", fieldtype="Link", options="BOM", insert_after="custom_bom_code", read_only=1, no_copy=1),
        dict(fieldname="custom_version_no", label="版本号", fieldtype="Int", insert_after="custom_version_source", read_only=1, no_copy=1),
    ]}, update=True)
    frappe.db.updatedb("BOM")
    frappe.clear_cache(doctype="BOM")


def lock_item(item):
    frappe.db.sql("select name from `tabItem` where name=%s for update", item)


def validate_version(doc, method=None):
    previous = doc.get_doc_before_save()
    if doc.get("custom_first_activated_at") != (previous.get("custom_first_activated_at") if previous else None):
        frappe.throw("首次启用时间由系统记录，不允许修改。")
    if previous and (previous.get("custom_version_source") != doc.get("custom_version_source") or cint(previous.get("custom_version_no")) != cint(doc.get("custom_version_no"))):
        frappe.throw("版本来源和版本号不允许修改。")
    if not doc.get("custom_version_source"):
        return
    source = frappe.get_doc("BOM", doc.custom_version_source)
    source.check_permission("read")
    if source.docstatus != 1 or not source.is_active:
        frappe.throw("更新来源必须是已提交且有效的 BOM。")
    if source.item != doc.item or source.company != doc.company or doc.get("amended_from"):
        frappe.throw("新版本必须保留来源物料、公司，且不能同时使用取消修订来源。")
    if cint(doc.custom_version_no) <= cint(source.get("custom_version_no") or 1):
        frappe.throw("新版本号必须大于来源版本。")
    if doc.docstatus == 0 and doc.is_default:
        frappe.throw("新版本草稿不能设为默认，请使用保存并启用。")


def name_version(doc):
    lock_item(doc.item)
    validate_version(doc)
    if frappe.db.exists("BOM", {"custom_version_source": doc.custom_version_source, "docstatus": 0}):
        frappe.throw("来源版本已有更新草稿，请先处理现有草稿。")
    versions = frappe.get_all("BOM", filters={"item": doc.item}, fields=["custom_version_no"])
    doc.custom_version_no = max([len(versions)] + [cint(v.custom_version_no) for v in versions]) + 1
    code = doc.custom_bom_code or "BOM-" + frappe.db.get_value("Item", doc.item, "item_code")
    suffix = 1
    while frappe.db.exists("BOM", f"{code}-{suffix}"):
        suffix += 1
    doc.name = f"{code}-{suffix}"
    if len(doc.name) > 140:
        frappe.throw("物料编码过长，无法生成版本单号。")


@frappe.whitelist()
def create_update_version(source_bom):
    source = frappe.get_doc("BOM", source_bom)
    source.check_permission("read")
    frappe.has_permission("BOM", "create", throw=True)
    lock_item(source.item)
    source.reload()
    if source.docstatus != 1 or not source.is_active:
        frappe.throw("只能更新已提交且有效的 BOM。")
    existing = frappe.db.get_value("BOM", {"custom_version_source": source.name, "docstatus": 0}, "name")
    if existing:
        frappe.get_doc("BOM", existing).check_permission("read")
        return existing
    versions = frappe.get_all("BOM", filters={"item": source.item}, fields=["custom_version_no"])
    draft = frappe.copy_doc(source)
    draft.docstatus = 0
    draft.custom_first_activated_at = None
    draft.amended_from = None
    draft.is_default = 0
    draft.is_active = 1
    draft.custom_version_source = source.name
    draft.custom_version_no = max([len(versions)] + [cint(v.custom_version_no) for v in versions]) + 1
    draft.insert()
    return draft.name


def before_submit(doc, method=None):
    if not doc.get("custom_version_source"):
        return
    lock_item(doc.item)
    validate_version(doc)
    current = frappe.db.get_value("Item", doc.item, "default_bom")
    if current and current != doc.custom_version_source:
        frappe.throw("默认 BOM 已改变，请从当前默认版本重新创建更新版本。")
    doc.is_active = 1
    doc.is_default = 1


@frappe.whitelist()
def activate_bom_version(bom):
    doc = frappe.get_doc("BOM", bom)
    doc.check_permission("write")
    doc.check_permission("submit")
    if doc.docstatus != 0 or not doc.get("custom_version_source"):
        frappe.throw("只能启用更新版本草稿。")
    doc.submit()
    return doc.name


def on_cancel(doc, method=None):
    if not doc.get("custom_version_source"):
        return
    lock_item(doc.item)
    if frappe.db.get_value("Item", doc.item, "default_bom"):
        return
    rows = frappe.get_all("BOM", filters={"item": doc.item, "docstatus": 1, "is_active": 1}, order_by="creation desc", pluck="name", limit=1)
    if rows:
        previous = frappe.get_doc("BOM", rows[0])
        previous.is_default = 1
        previous.manage_default_bom()


def before_cancel(doc, method=None):
    if doc.get("custom_version_source"):
        lock_item(doc.item)


def record_activation(doc, method=None):
    if (doc.docstatus == 1 and doc.is_active and doc.is_default
            and frappe.db.get_value("Item", doc.item, "default_bom") == doc.name
            and not doc.get("custom_first_activated_at")):
        from frappe.utils import now_datetime
        doc.db_set("custom_first_activated_at", now_datetime(), update_modified=False)


@frappe.whitelist()
def get_bom_version_diff(source_bom, target_bom):
    docs = [frappe.get_doc("BOM", name) for name in (source_bom, target_bom)]
    for doc in docs:
        doc.check_permission("read")
    if docs[0].item != docs[1].item:
        frappe.throw("只能比较同一物料的版本。")
    return {key: {"items": [dict(item_code=r.item_code, qty=r.qty, bom_no=r.bom_no) for r in doc.items], "operations": [dict(operation=r.operation, time_in_mins=r.time_in_mins) for r in doc.operations]} for key, doc in zip(("before", "after"), docs)}


@frappe.whitelist()
def switch_draft_work_order_bom(work_order, target_bom):
    frappe.db.sql("select name from `tabWork Order` where name=%s for update", work_order)
    wo = frappe.get_doc("Work Order", work_order)
    wo.check_permission("write")
    target = frappe.get_doc("BOM", target_bom)
    target.check_permission("read")
    lock_item(wo.production_item)
    if wo.docstatus != 0 or any(frappe.db.exists(dt, {"work_order": wo.name, "docstatus": ["<", 2]}) for dt in ("Stock Entry", "Job Card")):
        frappe.throw("仅未执行的草稿工单允许切换版本。")
    if frappe.db.exists("DocType", "Layered Supply Allocation") and frappe.db.exists("Layered Supply Allocation", {"work_order": wo.name}):
        frappe.throw("工单已有补料分配记录，不能切换 BOM。")
    if wo.get("custom_parent_work_order"):
        frappe.throw("分层子工单必须保留父 BOM 指定的版本，不能独立切换默认 BOM。")
    if target.item != wo.production_item or target.company != wo.company or target.docstatus != 1 or not target.is_active or frappe.db.get_value("Item", wo.production_item, "default_bom") != target.name:
        frappe.throw("目标必须是同物料、同公司的当前有效默认 BOM。")
    wo.bom_no = target.name
    wo.get_items_and_operations_from_bom()
    wo.save()
    return wo.name
