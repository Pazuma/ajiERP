"""Read-only exports for selected document reconciliation."""

import json
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.utils.xlsxutils import make_xlsx
from frappe.desk.utils import provide_binary_file

MAX_DOCUMENTS = 500

EXPORT_CONFIG = {
	"Purchase Order": {
		"date_field": "transaction_date",
		"party_field": "supplier_name",
		"party_fallback_field": "supplier",
		"party_label": "供应商",
		"date_label": "订单日期",
		"number_label": "采购订单号",
		"allowed_docstatus": {0, 1},
		"cancelled_status": "Cancelled",
		"extra_field": "schedule_date",
		"extra_label": "预计交货日期",
		"file_prefix": "采购订单",
	},
	"Delivery Note": {
		"date_field": "posting_date",
		"party_field": "customer_name",
		"party_fallback_field": "customer",
		"party_label": "客户",
		"date_label": "出货日期",
		"number_label": "出货单号",
		"allowed_docstatus": {1},
		"cancelled_status": "Cancelled",
		"extra_field": "warehouse",
		"extra_label": "出库仓库",
		"file_prefix": "客户出货",
	},
}


def _parse_names(document_names):
	if isinstance(document_names, str):
		document_names = json.loads(document_names)
	if not isinstance(document_names, list):
		frappe.throw(_("单据选择参数无效。"))
	names = list(dict.fromkeys(str(name).strip() for name in document_names if str(name).strip()))
	if not names:
		frappe.throw(_("请至少选择一张单据。"))
	if len(names) > MAX_DOCUMENTS:
		frappe.throw(_("单次最多导出 {0} 张单据。请缩小选择范围。").format(MAX_DOCUMENTS))
	return names


def _row_value(row, fieldname):
	return row.get(fieldname) if fieldname else ""


@frappe.whitelist()
def download_reconciliation_export(document_type: str, document_names):
	config = EXPORT_CONFIG.get(document_type)
	if not config:
		frappe.throw(_("不支持的对账导出单据类型。"))
	names = _parse_names(document_names)
	rows = []
	skipped = []
	valid_count = 0

	for name in names:
		try:
			doc = frappe.get_doc(document_type, name)
			frappe.has_permission(document_type, "read", doc=doc, throw=True)
		except (frappe.DoesNotExistError, frappe.PermissionError):
			skipped.append([name, "无读取权限或单据不存在"])
			continue
		if doc.docstatus not in config["allowed_docstatus"]:
			skipped.append([name, "单据状态不符合导出要求"])
			continue
		if getattr(doc, "status", None) == config["cancelled_status"]:
			skipped.append([name, "已取消"])
			continue
		valid_count += 1
		for item in doc.get("items") or []:
			if not item.item_code:
				continue
			amount = _row_value(item, "amount")
			rows.append([
				name, getattr(doc, config["date_field"], ""),
				getattr(doc, config["party_field"], "") or getattr(doc, config["party_fallback_field"], ""),
				item.item_code, item.item_name, item.stock_uom or item.uom, item.rate, item.qty,
				amount, _row_value(item, config["extra_field"]),
			])

	if not valid_count:
		frappe.throw(_("所选单据均不符合导出条件。"))

	headers = [config["number_label"], config["date_label"], config["party_label"], "物料编码", "物料名称", "库存单位", "单价", "数量", "金额", config["extra_label"]]
	metadata = [
		["导出时间", now_datetime().strftime("%Y-%m-%d %H:%M:%S")],
		["导出人", frappe.session.user],
		["所选单据数", len(names)],
		["成功单据数", valid_count],
		["明细行数", len(rows)],
		[],
		["单据号", "跳过原因"],
		*skipped,
	]
	from io import BytesIO
	import xlsxwriter
	output = BytesIO()
	wb = xlsxwriter.Workbook(output, {"constant_memory": True, "default_date_format": "yyyy-mm-dd"})
	make_xlsx([headers, *rows], "对账明细", wb=wb, column_widths=[22, 14, 24, 18, 28, 12, 14, 12, 14, 20])
	make_xlsx(metadata, "导出说明", wb=wb, column_widths=[20, 40])
	wb.close()
	output.seek(0)
	provide_binary_file(
		f"{config['file_prefix']}-对账明细-{datetime.now():%Y%m%d%H%M%S}",
		"xlsx",
		output.getvalue(),
	)
