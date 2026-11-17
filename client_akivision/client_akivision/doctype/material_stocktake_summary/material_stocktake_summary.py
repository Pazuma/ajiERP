"""Warehouse-facing stocktake document.

The document records a physical count; ERPNext's Stock Reconciliation remains
the sole writer of stock ledger and accounting records.
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowtime, today
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import build_xlsx_response, read_xls_file_from_attached_file, read_xlsx_file_from_attached_file

from erpnext.stock.utils import get_stock_balance


EXCEL_HEADERS = ("物料编码", "物料名称", "仓库", "库存单位", "实盘数量", "差异原因", "差异说明", "备注")


class MaterialStocktakeSummary(Document):
	def validate(self):
		self._set_defaults()
		self._validate_warehouses()
		self._validate_items(require_counted_qty=False)

	def before_submit(self):
		self._validate_warehouses()
		self._validate_items(require_counted_qty=True)
		self._validate_snapshot_is_current()

	def on_submit(self):
		if self.stock_reconciliation:
			frappe.throw(_("库存已经更新，关联调账单：{0}").format(self.stock_reconciliation))
		reconciliation = self._create_stock_reconciliation()
		self.db_set("stock_reconciliation", reconciliation.name)
		self.db_set("status", "已调整")

	def on_cancel(self):
		self.db_set("status", "已取消")

	def _set_defaults(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company")
		if not self.posting_date:
			self.posting_date = today()
		if not self.posting_time:
			self.posting_time = nowtime()
		if not self.counted_by:
			self.counted_by = frappe.session.user
		if not self.status:
			self.status = "草稿"

	def _validate_warehouses(self):
		if not self.warehouses:
			frappe.throw(_("请至少选择一个盘点仓库。"))
		seen = set()
		for row in self.warehouses:
			if not row.warehouse:
				frappe.throw(_("仓库行 {0} 未选择仓库。").format(row.idx))
			if row.warehouse in seen:
				frappe.throw(_("仓库 {0} 重复。").format(row.warehouse))
			seen.add(row.warehouse)
			warehouse = frappe.db.get_value("Warehouse", row.warehouse, ["company", "is_group", "disabled"], as_dict=True)
			if not warehouse or warehouse.company != self.company or warehouse.is_group or warehouse.disabled:
				frappe.throw(_("仓库 {0} 必须是本公司的启用末级仓库。").format(row.warehouse))

	def _validate_items(self, require_counted_qty):
		if not self.items:
			frappe.throw(_("请生成或导入至少一条盘点明细。"))
		allowed_warehouses = {row.warehouse for row in self.warehouses}
		seen = set()
		for row in self.items:
			if not row.item_code or not row.warehouse:
				frappe.throw(_("明细行 {0} 必须填写物料和仓库。").format(row.idx))
			if row.warehouse not in allowed_warehouses:
				frappe.throw(_("明细行 {0} 的仓库不在本单盘点范围内。").format(row.idx))
			if not frappe.db.get_value("Item", row.item_code, "is_stock_item"):
				frappe.throw(_("明细行 {0} 的物料不是库存物料。").format(row.idx))
			key = (row.item_code, row.warehouse)
			if key in seen:
				frappe.throw(_("物料 {0} 在仓库 {1} 重复。" ).format(*key))
			seen.add(key)
			if require_counted_qty and row.get("counted_qty") is None:
				frappe.throw(_("明细行 {0} 未填写实盘数量。").format(row.idx))
			if row.get("counted_qty") is not None:
				row.qty_difference = flt(row.counted_qty) - flt(row.system_qty)
				row.amount_difference = row.qty_difference * flt(row.valuation_rate)
				if require_counted_qty and row.qty_difference:
					if not row.difference_reason:
						frappe.throw(_("明细行 {0} 有数量差异，必须填写差异原因。").format(row.idx))
					reason = frappe.db.get_value("Stocktake Difference Reason", row.difference_reason, ["enabled", "is_other"], as_dict=True)
					if not reason or not reason.enabled:
						frappe.throw(_("明细行 {0} 的差异原因不可用。").format(row.idx))
					if reason.is_other and not row.difference_note:
						frappe.throw(_("明细行 {0} 选择其他原因时必须填写差异说明。").format(row.idx))

	def _validate_snapshot_is_current(self):
		changed = []
		for row in self.items:
			current_qty, _rate = _stock_snapshot(row.item_code, row.warehouse, today(), nowtime())
			if flt(current_qty) != flt(row.system_qty):
				changed.append("{0} / {1}".format(row.item_code, row.warehouse))
		if changed:
			frappe.throw(_("盘点后账面库存已变化，请重新生成盘点行后再更新库存：{0}").format("、".join(changed)))

	def _create_stock_reconciliation(self):
		stock_reconciliation = frappe.get_doc({
			"doctype": "Stock Reconciliation",
			"company": self.company,
			"purpose": "Stock Reconciliation",
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"set_posting_time": self.set_posting_time,
			"items": [{
				"item_code": row.item_code,
				"warehouse": row.warehouse,
				"qty": row.counted_qty,
				"valuation_rate": row.valuation_rate,
				"stock_uom": row.stock_uom,
			} for row in self.items],
		})
		stock_reconciliation.insert()
		stock_reconciliation.submit()
		stock_reconciliation.add_comment("Info", _("由物料库存汇总清点单 {0} 自动生成。").format(self.name))
		return stock_reconciliation

	@frappe.whitelist()
	def generate_items(self):
		"""Append current stock rows for selected warehouses, without overwriting counts."""
		self._set_defaults()
		self._validate_warehouses()
		existing = {(row.item_code, row.warehouse) for row in self.items}
		for warehouse in (row.warehouse for row in self.warehouses):
			for item_code in frappe.get_all("Bin", filters={"warehouse": warehouse}, pluck="item_code", order_by="item_code"):
				if (item_code, warehouse) in existing:
					continue
				if not frappe.db.get_value("Item", item_code, "is_stock_item"):
					continue
				qty, rate = _stock_snapshot(item_code, warehouse, self.posting_date, self.posting_time)
				self.append("items", _item_row(item_code, warehouse, qty, rate))
		self.save()
		return {"rows": len(self.items)}

	@frappe.whitelist()
	def preview_import(self):
		return self._parse_import()

	@frappe.whitelist()
	def apply_import(self):
		result = self._parse_import()
		if result["errors"]:
			frappe.throw(_("Excel 存在错误，请修正后再导入。"))
		existing = {(row.item_code, row.warehouse): row for row in self.items}
		for data in result["valid_rows"]:
			row = existing.get((data["item_code"], data["warehouse"]))
			if not row:
				qty, rate = _stock_snapshot(data["item_code"], data["warehouse"], self.posting_date, self.posting_time)
				row = self.append("items", _item_row(data["item_code"], data["warehouse"], qty, rate))
			row.counted_qty = data["counted_qty"]
			row.difference_reason = data.get("difference_reason")
			row.difference_note = data.get("difference_note")
			row.qty_difference = flt(row.counted_qty) - flt(row.system_qty)
			row.amount_difference = row.qty_difference * flt(row.valuation_rate)
		self.save()
		return {"imported": len(result["valid_rows"]), "rows": len(self.items)}

	def _parse_import(self):
		if not self.import_file:
			frappe.throw(_("请先上传盘点 Excel 文件。"))
		data = _read_import_file(self.import_file)
		if not data:
			frappe.throw(_("Excel 文件没有数据。"))
		headers = [str(value or "").strip() for value in data[0]]
		missing = {"物料编码", "仓库", "实盘数量"} - set(headers)
		if missing:
			frappe.throw(_("Excel 缺少必要列：{0}").format("、".join(sorted(missing))))
		allowed = {row.warehouse for row in self.warehouses}
		valid_rows, errors, seen = [], [], set()
		for number, values in enumerate(data[1:], start=2):
			row = {headers[index]: values[index] if index < len(values) else None for index in range(len(headers))}
			if not any(str(value or "").strip() for value in row.values()):
				continue
			item_code, warehouse = str(row.get("物料编码") or "").strip(), str(row.get("仓库") or "").strip()
			try:
				counted_qty = flt(row.get("实盘数量"))
				if row.get("实盘数量") in (None, ""):
					raise ValueError
			except (TypeError, ValueError):
				errors.append({"row": number, "message": "实盘数量必须是数字"}); continue
			key = (item_code, warehouse)
			if key in seen:
				errors.append({"row": number, "message": "物料 + 仓库重复"}); continue
			seen.add(key)
			if warehouse not in allowed or not frappe.db.exists("Warehouse", warehouse):
				errors.append({"row": number, "message": "仓库不存在或不在本单范围"}); continue
			if not frappe.db.get_value("Item", item_code, "is_stock_item"):
				errors.append({"row": number, "message": "物料不存在或不是库存物料"}); continue
			reason = str(row.get("差异原因") or "").strip() or None
			valid_rows.append({"row": number, "item_code": item_code, "warehouse": warehouse, "counted_qty": counted_qty, "difference_reason": reason, "difference_note": str(row.get("差异说明") or "").strip()})
		return {"valid_rows": valid_rows, "errors": errors, "summary": {"valid": len(valid_rows), "errors": len(errors)}}


def _stock_snapshot(item_code, warehouse, posting_date, posting_time):
	return get_stock_balance(item_code, warehouse, posting_date, posting_time, with_valuation_rate=True)


def _item_row(item_code, warehouse, qty, rate):
	return {"item_code": item_code, "warehouse": warehouse, "system_qty": qty, "valuation_rate": rate, "snapshot_at": now_datetime()}


def _read_import_file(file_url):
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	extension = file_doc.get_extension()[1].lower().lstrip(".")
	if extension == "xlsx":
		return read_xlsx_file_from_attached_file(fcontent=content, read_only=True)
	if extension == "xls":
		return read_xls_file_from_attached_file(content)
	if extension == "csv":
		return read_csv_content(content, use_sniffer=True)
	frappe.throw(_("仅支持 XLSX、XLS 或 CSV 文件。"))


@frappe.whitelist()
def download_stocktake_template(name):
	"""Download the current document's stocktake rows as an editable Excel file."""
	doc = frappe.get_doc("Material Stocktake Summary", name)
	frappe.has_permission(doc.doctype, "read", doc=doc, throw=True)
	data = [list(EXCEL_HEADERS)] + [[
		row.item_code, row.item_name, row.warehouse, row.stock_uom, row.counted_qty if row.counted_qty is not None else "", row.difference_reason, row.difference_note, ""
	] for row in doc.items]
	build_xlsx_response(data, "物料库存盘点模板")


def ensure_stocktake_difference_reasons():
	"""Create the conservative default reason list without changing user data."""
	for reason_name, is_other in (
		("漏记出入库", 0),
		("收发记录延迟", 0),
		("报废或损耗", 0),
		("计量误差", 0),
		("库位误放", 0),
		("其他", 1),
	):
		if not frappe.db.exists("Stocktake Difference Reason", reason_name):
			frappe.get_doc({
				"doctype": "Stocktake Difference Reason",
				"reason_name": reason_name,
				"enabled": 1,
				"is_other": is_other,
			}).insert(ignore_permissions=True)
