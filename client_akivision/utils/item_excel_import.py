"""Three-column item import; native templates keep their existing behavior."""

import frappe

HEADERS = ("分类", "物料编码", "物料名称")
INSERT_OR_UPDATE = "Insert or Update Records"
DEFAULTS = {
	"is_sales_item": 0, "is_purchase_item": 1, "is_stock_item": 1,
	"disabled": 0, "is_fixed_asset": 0, "has_batch_no": 0,
	"has_serial_no": 0, "has_variants": 0, "allow_negative_stock": 0,
	"include_item_in_manufacturing": 1, "default_material_request_type": "Purchase",
	"end_of_life": "2099-12-31", "opening_stock": 0, "valuation_rate": 0,
	"standard_rate": 0,
}


def matches(file_url):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix
	rows = _raw_excel_matrix(file_url)
	return bool(rows and set(HEADERS).issubset({str(c or "").strip() for c in rows[0]}))


def stock_uom():
	uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
	if not frappe.db.exists("UOM", {"name": uom, "enabled": 1}):
		frappe.throw(f"默认库存单位 {uom} 不存在或未启用，请先设置库存设置中的默认单位。")
	return uom


def plan(file_url, import_type):
	from client_akivision.client_akivision.api.data_import import _raw_excel_matrix, _excel_text
	matrix = _raw_excel_matrix(file_url)
	headers = [str(c or "").strip() for c in (matrix[0] if matrix else [])]
	rows, warnings, seen = [], [], set()
	if set(headers) != set(HEADERS) or len(headers) != 3:
		warnings.append({"type": "error", "message": "三列物料表仅支持且必须包含：" + "、".join(HEADERS) + "。其他字段请使用标准模板。"})
	try:
		stock_uom()
	except frappe.ValidationError as exc:
		warnings.append({"type": "error", "message": str(exc)})
		frappe.clear_messages()
	for number, values in enumerate(matrix[1:], 2):
		if not any(v not in (None, "") for v in values):
			continue
		row = {h: _excel_text(values[i]) if i < len(values) else None for i, h in enumerate(headers)}
		row["excel_row"] = number
		try:
			if not all(row.get(h) for h in HEADERS):
				frappe.throw("分类、物料编码、物料名称均必填。")
			code = row["物料编码"]
			if code in seen:
				frappe.throw(f"文件中物料编码重复：{code}")
			seen.add(code)
			if not frappe.db.exists("Item Group", {"name": row["分类"], "is_group": 0}):
				frappe.throw(f"分类“{row['分类']}”不存在或为父分类，请先维护可用的物料分类。")
			exists = frappe.db.exists("Item", code)
			if import_type == "Insert New Records" and exists:
				frappe.throw(f"物料编码 {code} 已存在，请使用更新模式。")
			if import_type == "Update Existing Records" and not exists:
				frappe.throw(f"物料编码 {code} 不存在，不能更新。")
		except frappe.ValidationError as exc:
			warnings.append({"type": "error", "message": f"第 {number} 行：{exc}"})
			frappe.clear_messages()
		rows.append(row)
	if not rows:
		warnings.append({"type": "error", "message": "文件没有可导入的数据。"})
	return rows, warnings


def preview(file_url, import_type):
	rows, warnings = plan(file_url, import_type)
	return {"custom_mode": "item_three_columns", "columns": [{"header_title": h} for h in HEADERS],
		"data": [[r.get(h) or "" for h in HEADERS] for r in rows[:100]],
		"payload_count": len(rows), "warnings": warnings, "import_log": []}


def save_row(row, import_type):
	code = row["物料编码"]
	item = frappe.get_doc("Item", code) if (import_type == "Update Existing Records" or (import_type == INSERT_OR_UPDATE and frappe.db.exists("Item", code))) else frappe.new_doc("Item")
	if item.is_new():
		item.update(DEFAULTS)
		item.stock_uom = stock_uom()
	item.update({"item_code": code, "item_name": row["物料名称"], "item_group": row["分类"]})
	if item.is_new():
		item.description = row["物料名称"]
		item.insert(set_name=code)
	else:
		item.save()
	return item.name


def run(task):
	from frappe.core.doctype.data_import.importer import create_import_log
	rows, warnings = plan(task.import_file, task.import_type)
	if warnings:
		task.db_set("status", "Error")
		create_import_log(task.name, 0, {"success": False, "messages": warnings, "row_indexes": []})
		return {"status": "Error"}
	task.db_set("payload_count", len(rows))
	success = []
	for index, row in enumerate(rows):
		try:
			name = save_row(row, task.import_type)
			create_import_log(task.name, index, {"success": True, "docname": name, "row_indexes": [row["excel_row"]]})
			success.append(True)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			create_import_log(task.name, index, {"success": False, "exception": frappe.get_traceback(),
				"messages": frappe.local.message_log, "row_indexes": [row["excel_row"]]})
			frappe.clear_messages()
			success.append(False)
	status = "Success" if all(success) else "Partial Success" if any(success) else "Error"
	task.db_set("status", status)
	return {"name": task.name, "status": status}
