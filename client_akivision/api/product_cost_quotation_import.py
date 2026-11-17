"""Additive XLSX endpoints; existing costing APIs remain unchanged."""
import hashlib
import secrets

import frappe
from frappe.utils import cstr

from client_akivision.api.product_cost_quotation import _document
from client_akivision.utils.product_cost_import import parse, workbook


def _file(url):
    file = frappe.get_doc("File", {"file_url": url})
    file.check_permission("read")
    if not file.is_private or not file.file_name.lower().endswith(".xlsx"):
        frappe.throw("请上传私有XLSX文件")
    return file.get_content()


def _download(doc, kind, empty=False):
    doc.check_permission("export")
    frappe.local.response.filename = f"{doc.name}-{kind}-{'template' if empty else 'data'}.xlsx"
    frappe.local.response.filecontent = workbook(doc, kind, empty)
    frappe.local.response.type = "binary"


@frappe.whitelist()
def download_import_template(name, template_type="internal"):
    _download(_document(name), template_type, True)


@frappe.whitelist()
def export_import_data(name):
    _download(_document(name), "internal")


@frappe.whitelist(methods=["POST"])
def preview_import(name, file_url, expected_modified):
    doc = _document(name, write=True, expected_modified=expected_modified)
    data = _file(file_url)
    result = parse(data, doc)
    if not result["errors"]:
        candidate = frappe.get_doc(doc.as_dict())
        try:
            _update(candidate, result["changes"], {"main", "scenarios", "materials", "operations", "investments"})
            candidate.validate()
        except (frappe.ValidationError, ValueError) as exc:
            result["errors"].append(str(exc))
    token = secrets.token_urlsafe(32)
    frappe.cache.set_value("pcq-import:" + token, {"user": frappe.session.user, "name": name,
        "modified": cstr(doc.modified), "file_url": file_url, "digest": hashlib.sha256(data).hexdigest()}, expires_in_sec=600)
    return {**result, "preview_id": token}


def _update(doc, changes, groups):
    for change in changes:
        if change["group"] not in groups:
            continue
        target = doc if change["group"] == "main" else next((r for r in doc.get(change["group"]) if r.name == change["row_id"]), None)
        if target is None:
            target = doc.append(change["group"], {})
        target.update(change["values"])


@frappe.whitelist(methods=["POST"])
def apply_import(name, preview_id, expected_modified, selected_groups):
    key = "pcq-import:" + preview_id
    preview = frappe.cache.get_value(key)
    if not preview or preview["user"] != frappe.session.user or preview["name"] != name or preview["modified"] != expected_modified:
        frappe.throw("预览已失效，请重新上传预览")
    frappe.db.sql("select name from `tabProduct Cost Quotation` where name=%s for update", name)
    doc = _document(name, write=True, expected_modified=expected_modified)
    data = _file(preview["file_url"])
    if hashlib.sha256(data).hexdigest() != preview["digest"]:
        frappe.throw("文件已改变，请重新预览")
    result = parse(data, doc)
    if result["errors"]:
        frappe.throw("；".join(result["errors"]))
    groups = frappe.parse_json(selected_groups)
    if not isinstance(groups, list) or not groups or set(groups) - {"main", "scenarios", "materials", "operations", "investments"}:
        frappe.throw("请选择有效导入分组")
    frappe.db.savepoint("pcq_import")
    try:
        _update(doc, result["changes"], groups)
        doc.estimate_acknowledged = 0
        doc.save()
    except Exception:
        frappe.db.rollback(save_point="pcq_import")
        raise
    frappe.cache.delete_value(key)
    return {"name": doc.name, "modified": doc.modified}
