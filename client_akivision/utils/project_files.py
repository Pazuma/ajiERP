"""Validation and audit logging for PDF files stored on Project."""

from pathlib import PurePosixPath

import frappe
from frappe import _
from frappe.utils import escape_html, now


FIELDNAME = "custom_project_files"


def _rows(doc):
	return list(doc.get(FIELDNAME) or [])


def _file_name(file_doc):
	return file_doc.file_name or PurePosixPath(file_doc.file_url or "").name


def _get_file(file_url):
	if not file_url or not str(file_url).startswith("/private/files/"):
		frappe.throw(_("项目文件必须上传为私有 PDF。"))

	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		frappe.throw(_("找不到项目文件 {0}，请重新上传。").format(escape_html(file_url)))
	return frappe.get_doc("File", name)


def _validate_pdf(file_doc):
	file_name = _file_name(file_doc)
	if not file_name.lower().endswith(".pdf"):
		frappe.throw(_("项目文件 {0} 不是 PDF。").format(escape_html(file_name)))
	if not file_doc.is_private:
		frappe.throw(_("项目文件必须保存为私有文件。"))

	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode()
	if not content.lstrip().startswith(b"%PDF-"):
		frappe.throw(_("项目文件 {0} 的内容不是有效 PDF。").format(escape_html(file_name)))


def validate_project_files(doc, method=None):
	"""Validate file ownership and populate server-controlled audit fields."""
	previous = doc.get_doc_before_save()
	previous_by_name = {row.name: row for row in _rows(previous)} if previous else {}

	for row in _rows(doc):
		file_doc = _get_file(row.pdf_file)
		_validate_pdf(file_doc)
		if file_doc.attached_to_doctype != "Project" or file_doc.attached_to_name != doc.name:
			frappe.throw(_("项目文件 {0} 未绑定到当前项目。").format(escape_html(_file_name(file_doc))))

		old_row = previous_by_name.get(row.name)
		if old_row and old_row.pdf_file == row.pdf_file:
			row.uploaded_by = old_row.uploaded_by
			row.uploaded_on = old_row.uploaded_on
		else:
			row.uploaded_by = frappe.session.user
			row.uploaded_on = now()
		row.file_name = (row.file_name or _file_name(file_doc)).strip()


def _row_map(doc):
	return {row.name: row for row in _rows(doc) if row.name}


def _display_name(row):
	return escape_html(row.file_name or PurePosixPath(row.pdf_file or "").name or _("未命名文件"))


def _add_log(doc, message):
	doc.add_comment("Info", message)


def _delete_unreferenced_file(doc, row):
	if not row.pdf_file:
		return
	if frappe.db.exists("Project File Item", {"pdf_file": row.pdf_file}):
		return
	name = frappe.db.get_value(
		"File",
		{
			"file_url": row.pdf_file,
			"attached_to_doctype": "Project",
			"attached_to_name": doc.name,
		},
		"name",
	)
	if name:
		frappe.delete_doc("File", name, ignore_permissions=True)


def log_project_file_changes(doc, method=None):
	"""Write explicit file changes to the Project timeline after a successful save."""
	previous = doc.get_doc_before_save()
	if not previous:
		for row in _rows(doc):
			_add_log(doc, _("上传了项目文件：{0}").format(_display_name(row)))
		return

	before = _row_map(previous)
	after = _row_map(doc)
	for name, row in after.items():
		old_row = before.get(name)
		if not old_row:
			_add_log(doc, _("上传了项目文件：{0}").format(_display_name(row)))
		elif old_row.pdf_file != row.pdf_file:
			_add_log(doc, _("替换了项目文件：{0}").format(_display_name(row)))
			_delete_unreferenced_file(doc, old_row)
		elif old_row.file_name != row.file_name or old_row.remarks != row.remarks:
			_add_log(doc, _("修改了项目文件名称或备注：{0}").format(_display_name(row)))

	for name, row in before.items():
		if name not in after:
			_add_log(doc, _("删除了项目文件：{0}").format(_display_name(row)))
			_delete_unreferenced_file(doc, row)
