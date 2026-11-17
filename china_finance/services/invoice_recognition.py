import hashlib
import json
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from china_finance.services.archive import get_file_doc
from china_finance.services.invoice_recognition_provider import get_provider


ALLOWED_ROLES = ("System Manager", "Accounts Manager", "China Tax User")
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".ofd"}
INVOICE_FIELDS = (
	"invoice_type", "invoice_number", "invoice_code", "invoice_date", "seller_name", "seller_tax_id",
	"buyer_name", "buyer_tax_id", "currency", "invoice_status",
)


def _require_role():
	frappe.only_for(ALLOWED_ROLES)


@frappe.whitelist()
def create_recognition(company, direction, source_file):
	"""Create a Draft recognition record after validating the supplied File URL."""
	_require_role()
	if direction not in ("进项", "销项"):
		frappe.throw(_("进销项必须为进项或销项"))
	_validate_file(company, source_file)
	doc = frappe.get_doc({
		"doctype": "China Tax Invoice Recognition", "company": company, "direction": direction,
		"source_file": source_file,
	})
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
def recognize_invoice_for_form(company, direction, source_file):
	"""Synchronously recognize an attachment for an unsaved invoice form.

	A recognition task is retained for traceability, while no formal invoice is
	created until the user saves the current form.
	"""
	_require_role()
	if direction not in ("进项", "销项"):
		frappe.throw(_("进销项必须为进项或销项"))
	settings = _get_settings(company)
	if not cint(settings.invoice_recognition_enabled):
		frappe.throw(_("当前公司未启用发票识别"))
	file_doc = _validate_file(company, source_file, settings)
	content = file_doc.get_content()
	content = content.encode("utf-8") if isinstance(content, str) else content
	file_hash = hashlib.sha256(content).hexdigest()
	existing = frappe.db.get_value("China Tax Invoice Recognition", {"file_hash": file_hash, "status": ("in", ("Queued", "Processing", "Completed", "Needs Review", "Converted"))}, "name")
	if existing:
		existing_doc = frappe.get_doc("China Tax Invoice Recognition", existing)
		if existing_doc.recognized_data:
			data = json.loads(existing_doc.recognized_data)
			return {"task": existing, "data": data, "warnings": (existing_doc.warnings or "").splitlines(), "duplicate_invoice": find_duplicate_invoice(data, direction), "file_hash": file_hash, "provider_request_id": existing_doc.provider_request_id}
	provider = get_provider(settings)
	result = provider.recognize(file_doc, {"company": company, "direction": direction})
	data = normalize_recognition_result(result, direction)
	warnings = [str(warning) for warning in (result.get("warnings") or [])]
	warnings.extend(warning for warning in validate_recognized_data(data, direction) if warning not in warnings)
	duplicate = find_duplicate_invoice(data, direction)
	if duplicate:
		warnings.append(_("发现已存在的税务发票：{0}").format(duplicate))
	task = frappe.get_doc({
		"doctype": "China Tax Invoice Recognition", "company": company, "direction": direction,
		"source_file": source_file, "file_hash": file_hash, "status": "Needs Review" if warnings else "Completed",
		"provider": provider.name, "provider_request_id": str(result.get("request_id") or ""),
		"recognized_data": json.dumps(data, ensure_ascii=False), "confidence_score": flt(data.get("confidence_score"), 2),
		"warnings": "\n".join(warnings), "validation_summary": _validation_summary(data, warnings),
		"started_on": now_datetime(), "completed_on": now_datetime(),
	})
	task.flags.allow_recognition_result_insert = True
	task.insert()
	return {"task": task.name, "data": data, "warnings": warnings, "duplicate_invoice": duplicate, "file_hash": file_hash, "provider_request_id": task.provider_request_id}


@frappe.whitelist()
def recognize_invoice(name):
	_require_role()
	doc = frappe.get_doc("China Tax Invoice Recognition", name)
	doc.check_permission("write")
	if doc.status not in ("Draft", "Failed", "Needs Review"):
		frappe.throw(_("当前状态不允许发起识别"))
	settings = _get_settings(doc.company)
	if not cint(settings.invoice_recognition_enabled):
		frappe.throw(_("当前公司未启用发票识别"))
	_validate_file(doc.company, doc.source_file, settings)
	existing = frappe.db.get_value(
		"China Tax Invoice Recognition",
		{"file_hash": doc.file_hash, "name": ("!=", doc.name), "status": ("in", ("Queued", "Processing", "Completed", "Needs Review", "Converted"))},
		"name",
	)
	if existing:
		frappe.throw(_("该电子原件已有识别任务：{0}").format(existing))
	doc.db_set("status", "Queued", update_modified=False)
	doc.db_set("error_message", None, update_modified=False)
	frappe.enqueue("china_finance.services.invoice_recognition.run_invoice_recognition", queue="short", job_name=f"invoice-recognition:{doc.name}", name=doc.name)
	return {"name": doc.name, "status": "Queued"}


def run_invoice_recognition(name):
	"""Queue worker entry point. It always preserves the task and records failure."""
	doc = frappe.get_doc("China Tax Invoice Recognition", name)
	if doc.status != "Queued":
		return
	doc.db_set("status", "Processing", update_modified=False)
	doc.db_set("started_on", now_datetime(), update_modified=False)
	try:
		settings = _get_settings(doc.company)
		file_doc = _validate_file(doc.company, doc.source_file, settings)
		provider = get_provider(settings)
		result = provider.recognize(file_doc, {"company": doc.company, "direction": doc.direction})
		data = normalize_recognition_result(result, doc.direction)
		warnings = validate_recognized_data(data, doc.direction)
		duplicate = find_duplicate_invoice(data, doc.direction)
		if duplicate:
			warnings.append(_("发现已存在的税务发票：{0}，不能生成重复草稿").format(duplicate))
		doc.db_set("provider", provider.name, update_modified=False)
		doc.db_set("provider_request_id", str(result.get("request_id") or ""), update_modified=False)
		doc.db_set("recognized_data", json.dumps(data, ensure_ascii=False), update_modified=False)
		doc.db_set("confidence_score", flt(data.get("confidence_score"), 2), update_modified=False)
		doc.db_set("warnings", "\n".join(warnings), update_modified=False)
		doc.db_set("validation_summary", _validation_summary(data, warnings), update_modified=False)
		doc.db_set("status", "Needs Review" if warnings else "Completed", update_modified=False)
		doc.db_set("completed_on", now_datetime(), update_modified=False)
	except Exception as exc:
		frappe.db.rollback()
		frappe.db.set_value("China Tax Invoice Recognition", name, {
			"status": "Failed", "completed_on": now_datetime(), "error_message": str(exc),
		}, update_modified=False)
		frappe.db.commit()
		frappe.log_error(title=f"Invoice recognition failed: {name}", message=frappe.get_traceback())


@frappe.whitelist()
def create_tax_invoice_draft_from_recognition(name):
	_require_role()
	recognition = frappe.get_doc("China Tax Invoice Recognition", name)
	recognition.check_permission("write")
	if recognition.tax_invoice:
		return {"name": recognition.tax_invoice}
	if recognition.status not in ("Completed", "Needs Review"):
		frappe.throw(_("只有已完成或待核对的识别任务可以生成发票草稿"))
	data = json.loads(recognition.recognized_data or "{}")
	warnings = validate_recognized_data(data, recognition.direction)
	duplicate = find_duplicate_invoice(data, recognition.direction)
	if duplicate:
		frappe.throw(_("已存在相同税务发票：{0}").format(duplicate))
	if _missing_required(data):
		frappe.throw(_("识别结果缺少必填信息，请重新识别或手工新建税务发票"))
	invoice = frappe.get_doc({
		"doctype": "China Tax Invoice", "company": recognition.company, "direction": recognition.direction,
		"source_system": "Invoice Recognition", "source_id": recognition.name,
		"original_file": recognition.source_file, "recognition_task": recognition.name,
		"invoice_status": data.get("invoice_status") or "蓝票", "currency": data.get("currency") or "CNY",
		"items": data["items"], **{field: data.get(field) for field in INVOICE_FIELDS if data.get(field)},
	})
	invoice.insert()
	recognition.db_set("tax_invoice", invoice.name, update_modified=False)
	recognition.db_set("status", "Converted", update_modified=False)
	return {"name": invoice.name, "warnings": warnings}


def normalize_recognition_result(result, direction):
	data = result.get("data", result)
	if not isinstance(data, dict):
		frappe.throw(_("识别服务未返回发票对象"))
	normalized = {field: data.get(field) for field in INVOICE_FIELDS}
	normalized["currency"] = normalized["currency"] or "CNY"
	normalized["invoice_status"] = normalized["invoice_status"] or "蓝票"
	normalized["confidence_score"] = flt(data.get("confidence_score"), 2)
	normalized["items"] = []
	for item in data.get("items") or []:
		if not isinstance(item, dict):
			continue
		normalized["items"].append({
			"item_name": item.get("item_name"), "specification": item.get("specification"), "unit": item.get("unit"),
			"quantity": flt(item.get("quantity")), "unit_price": flt(item.get("unit_price")),
			"net_amount": flt(item.get("net_amount"), 2), "tax_rate": flt(item.get("tax_rate")),
			"tax_amount": flt(item.get("tax_amount"), 2), "goods_service_code": item.get("goods_service_code"),
		})
	normalized["direction"] = direction
	return normalized


def validate_recognized_data(data, direction):
	warnings = []
	missing = _missing_required(data)
	if missing:
		warnings.append(_("缺少必填字段：{0}").format("、".join(missing)))
	if not data.get("items"):
		warnings.append(_("未识别到发票明细"))
	if data.get("currency") != "CNY":
		warnings.append(_("首期仅支持人民币发票，请人工核对币种"))
	allowed_types = {"数电专用发票", "数电普通发票", "增值税专用发票", "增值税普通发票", "机动车销售统一发票", "其他"}
	if data.get("invoice_type") not in allowed_types:
		warnings.append(_("发票类型无法映射，请在草稿中选择正确类型"))
	if data.get("invoice_status") not in {"蓝票", "红票", "作废"}:
		warnings.append(_("票据状态无法映射，请在草稿中核对"))
	for index, item in enumerate(data.get("items") or [], 1):
		if not item.get("item_name"):
			warnings.append(_("第 {0} 条明细缺少货物或服务名称").format(index))
	return warnings


def find_duplicate_invoice(data, direction):
	if not data.get("seller_tax_id") or not data.get("invoice_number"):
		return None
	key = "|".join((direction, data["seller_tax_id"].strip().upper(), data["invoice_number"].strip().upper()))
	return frappe.db.get_value("China Tax Invoice", {"invoice_key": key}, "name")


def _missing_required(data):
	labels = {"invoice_type": _("发票类型"), "invoice_number": _("发票号码"), "invoice_date": _("开票日期"), "seller_name": _("销售方名称"), "seller_tax_id": _("销售方税号"), "buyer_name": _("购买方名称")}
	return [label for field, label in labels.items() if not data.get(field)]


def _validation_summary(data, warnings):
	return _("识别到 {0} 条明细；{1}").format(len(data.get("items") or []), _("需人工核对") if warnings else _("基础校验通过"))


def _get_settings(company):
	settings = frappe.db.get_value("China Finance Settings", {"company": company, "enabled": 1}, "name")
	if not settings:
		frappe.throw(_("公司 {0} 未启用中国财务设置").format(company))
	return frappe.get_doc("China Finance Settings", settings)


def _validate_file(company, file_url, settings=None):
	file_doc = get_file_doc(file_url)
	if file_doc.attached_to_doctype and file_doc.attached_to_doctype not in ("China Tax Invoice Recognition", "China Tax Invoice"):
		frappe.throw(_("只能识别未绑定或属于发票识别流程的附件"))
	extension = Path(file_doc.file_name or file_url).suffix.lower()
	if extension not in ALLOWED_EXTENSIONS:
		frappe.throw(_("仅支持 PDF、PNG、JPG、JPEG、OFD 格式的发票文件"))
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")
	max_size = cint((settings.invoice_recognition_max_file_size_mb if settings else 10) or 10) * 1024 * 1024
	if len(content) > max_size:
		frappe.throw(_("发票文件超过最大允许大小 {0} MB").format(max_size // 1024 // 1024))
	if not _matches_file_signature(extension, content):
		frappe.throw(_("文件内容与扩展名不匹配"))
	return file_doc


def _matches_file_signature(extension, content):
	if extension == ".pdf":
		return content.startswith(b"%PDF-")
	if extension == ".png":
		return content.startswith(b"\x89PNG\r\n\x1a\n")
	if extension in (".jpg", ".jpeg"):
		return content.startswith(b"\xff\xd8\xff")
	if extension == ".ofd":
		return content.startswith(b"PK\x03\x04")
	return False
