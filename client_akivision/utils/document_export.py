"""Whitelisted, read-only exports for business documents and filtered lists."""
import json
from datetime import datetime
from io import BytesIO

import frappe
import xlsxwriter
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.xlsxutils import make_xlsx
from frappe.desk.utils import provide_binary_file

MAX_DOCUMENTS = 500
MAX_ROWS = 10000
CONFIG = {
	"Stock Entry": {"date": "posting_date", "party": "company", "child": "items", "fields": ["item_code", "item_name", "uom", "qty", "s_warehouse", "t_warehouse"]},
	"Material Stocktake Summary": {"date": "posting_date", "party": "company", "child": "items", "fields": ["item_code", "item_name", "warehouse", "system_qty", "counted_qty", "difference_qty", "difference_reason"]},
	"Work Order": {"date": "planned_start_date", "party": "company", "child": "required_items", "fields": ["item_code", "item_name", "required_qty", "transferred_qty", "source_warehouse", "warehouse"]},
	"Purchase Order": {"date": "transaction_date", "party": "supplier_name", "child": "items", "fields": ["item_code", "item_name", "uom", "rate", "qty", "amount", "schedule_date"]},
	"Purchase Receipt": {"date": "posting_date", "party": "supplier_name", "child": "items", "fields": ["item_code", "item_name", "uom", "rate", "qty", "amount", "warehouse"]},
	"Sales Order": {"date": "transaction_date", "party": "customer_name", "child": "items", "fields": ["item_code", "item_name", "uom", "rate", "qty", "amount", "delivery_date"]},
	"Delivery Note": {"date": "posting_date", "party": "customer_name", "child": "items", "fields": ["item_code", "item_name", "uom", "rate", "qty", "amount", "warehouse"]},
	"BOM": {"date": "creation", "party": "item", "child": "items", "fields": ["item_code", "item_name", "uom", "qty", "rate", "amount"]},
}

def _names(value):
	if isinstance(value, str): value = json.loads(value)
	if not isinstance(value, list): frappe.throw(_("单据选择参数无效。"))
	value = list(dict.fromkeys(str(v).strip() for v in value if str(v).strip()))
	if not value: frappe.throw(_("请至少选择一条记录。"))
	if len(value) > MAX_DOCUMENTS: frappe.throw(_("单次最多导出 {0} 条记录。" ).format(MAX_DOCUMENTS))
	return value

def _response(rows, sheet, prefix, notes):
	if len(rows) > MAX_ROWS: frappe.throw(_("导出结果超过 {0} 行，请缩小筛选范围。" ).format(MAX_ROWS))
	out = BytesIO(); wb = xlsxwriter.Workbook(out, {"constant_memory": True, "default_date_format": "yyyy-mm-dd"})
	widths = []
	for column in zip(*rows):
		widths.append(min(36, max(12, max(len(str(value or "")) for value in column) + 2)))
	make_xlsx(rows, sheet, wb=wb, column_widths=widths)
	make_xlsx([["导出时间", now_datetime().strftime("%Y-%m-%d %H:%M:%S")], ["导出人", frappe.session.user], [], ["记录", "说明"], *notes], "导出说明", wb=wb, column_widths=[24, 42])
	detail_sheet = wb.worksheets()[0]
	detail_sheet.freeze_panes(1, 0)
	detail_sheet.autofilter(0, 0, max(0, len(rows) - 1), max(0, len(rows[0]) - 1))
	wb.close()
	provide_binary_file(f"{prefix}-{datetime.now():%Y%m%d%H%M%S}", "xlsx", out.getvalue())

@frappe.whitelist()
def download_document_export(document_type, document_names=None, filters=None):
	if document_type == "Item":
		return _download_item_export(document_names, filters)
	if document_type not in CONFIG: frappe.throw(_("暂不支持该单据类型导出。"))
	names = _names(document_names) if document_names else None
	if not names:
		condition = json.loads(filters or "{}")
		allowed = {"company", "customer", "supplier", "status", "warehouse", "item_code", "from_date", "to_date"}
		condition = {k: v for k, v in condition.items() if k in allowed and v not in (None, "")}
		names = frappe.get_list(document_type, filters=condition, pluck="name", limit_page_length=MAX_DOCUMENTS)
		if not names: frappe.throw(_("筛选条件没有匹配记录。"))
	config = CONFIG[document_type]
	parent_meta = frappe.get_meta(document_type)
	child_meta = frappe.get_meta(parent_meta.get_field(config["child"]).options)
	label = lambda meta, fieldname, fallback: (meta.get_field(fieldname).label if meta.get_field(fieldname) else fallback)
	headers = ["单据号", label(parent_meta, config["date"], "日期"), label(parent_meta, config["party"], "对象")]
	headers += [label(child_meta, fieldname, fieldname) for fieldname in config["fields"]]
	rows = [headers]; notes = []; valid = 0
	for name in names:
		try:
			doc = frappe.get_doc(document_type, name); frappe.has_permission(document_type, "read", doc=doc, throw=True)
		except (frappe.DoesNotExistError, frappe.PermissionError): notes.append([name, "无权限或记录不存在"]); continue
		if getattr(doc, "docstatus", 0) == 2: notes.append([name, "已取消"]); continue
		valid += 1
		for child in doc.get(config["child"]) or []:
			rows.append([name, doc.get(config["date"]) or "", doc.get(config["party"]) or ""] + [child.get(f) or "" for f in config["fields"]])
	if not valid: frappe.throw(_("没有可导出的记录。"))
	_response(rows, "数据明细", document_type, notes)


def _download_item_export(document_names=None, filters=None):
	frappe.has_permission("Item", "read", throw=True)
	fields = ["name", "item_name", "item_group", "brand", "stock_uom", "description",
		"custom_product_name", "custom_internal_model", "custom_external_model"]
	conditions = frappe.parse_json(filters or "[]")
	if not isinstance(conditions, (dict, list)):
		frappe.throw(_("筛选条件无效。"))
	names = _names(document_names) if document_names else None
	if names:
		conditions = [["Item", "name", "in", names]]
	items = frappe.get_list("Item", filters=conditions, fields=fields, limit_page_length=MAX_DOCUMENTS + 1)
	if len(items) > MAX_DOCUMENTS:
		frappe.throw(_("导出记录过多，请缩小筛选范围。"))
	if not items:
		frappe.throw(_("没有可导出的记录。"))
	meta = frappe.get_meta("Item")
	headers = [(meta.get_field(field).label if meta.get_field(field) else _("物料编码")) for field in fields]
	_response([headers, *[[row.get(field) or "" for field in fields] for row in items]], "产品明细", "Item", [])
