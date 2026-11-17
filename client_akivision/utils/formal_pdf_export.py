"""Shared, read-only helpers for formal document PDF exports."""

import base64
import json
import shutil
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import frappe
from frappe import _
from frappe.desk.utils import provide_binary_file
from frappe.utils.pdf import get_pdf

MAX_DOCUMENTS = 100


def parse_names(document_names):
	if isinstance(document_names, str):
		document_names = json.loads(document_names)
	if not isinstance(document_names, list):
		frappe.throw(_("单据选择参数无效。"))
	names = list(dict.fromkeys(str(name).strip() for name in document_names if str(name).strip()))
	if not names:
		frappe.throw(_("请至少选择一张单据。"))
	if len(names) > MAX_DOCUMENTS:
		frappe.throw(_("单次最多生成 {0} 张单据。" ).format(MAX_DOCUMENTS))
	return names


def read_doc(doctype, name):
	doc = frappe.get_doc(doctype, name)
	frappe.has_permission(doctype, "read", doc=doc, throw=True)
	return doc


def logo_data_uri():
	path = Path(frappe.get_app_path("client_akivision", "public", "images", "aki_vision_logo.png"))
	if not path.exists():
		return ""
	return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def chinese_font_file_uri():
	path = Path(frappe.get_app_path("client_akivision", "public", "fonts", "wqy-zenhei.ttc"))
	if not path.exists():
		return ""
	return path.as_uri()


def ensure_chinese_pdf_font():
	"""Make bundled Chinese font visible to wkhtmltopdf/fontconfig.

	wkhtmltopdf is more reliable when CJK fonts are installed through fontconfig
	than when loading TTC fonts directly through @font-face. This copies the
	bundled font to the frappe user's local font directory, so all PDF templates
	that use "WenQuanYi Zen Hei" render Chinese text instead of tofu boxes.
	"""
	source = Path(frappe.get_app_path("client_akivision", "public", "fonts", "wqy-zenhei.ttc"))
	if not source.exists():
		return
	target_dir = Path.home() / ".local" / "share" / "fonts" / "client_akivision"
	target = target_dir / "wqy-zenhei.ttc"
	try:
		target_dir.mkdir(parents=True, exist_ok=True)
		if not target.exists() or target.stat().st_size != source.stat().st_size:
			shutil.copyfile(source, target)
			subprocess.run(["fc-cache", "-f", str(target_dir)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _("PDF 中文字体初始化失败"))


def render_pdf(template, context, orientation):
	ensure_chinese_pdf_font()
	context.setdefault("logo_data_uri", logo_data_uri())
	context.setdefault("chinese_font_file_uri", chinese_font_file_uri())
	html = frappe.render_template(template, context)
	# wkhtmltopdf requires both local-file access and an explicit allow-list for
	# assets referenced by file:// URLs, including embedded PDF fonts.
	public_dir = str(Path(frappe.get_app_path("client_akivision", "public")))
	return get_pdf(html, {"page-size": "A4", "orientation": orientation, "margin-top": "8mm", "margin-bottom": "8mm", "margin-left": "8mm", "margin-right": "8mm", "enable-local-file-access": "", "allow": public_dir})


def download_documents(files, prefix):
	"""Download one PDF directly, or preserve one-document-per-PDF in a ZIP."""
	if len(files) == 1:
		filename, content = files[0]
		provide_binary_file(filename, "pdf", content)
		return
	archive = BytesIO()
	with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
		for filename, content in files:
			bundle.writestr(f"{filename}.pdf", content)
	provide_binary_file(prefix, "zip", archive.getvalue())
