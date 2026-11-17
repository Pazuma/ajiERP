"""Export selected items and current, permission-filtered warehouse balances."""

from io import BytesIO

import frappe
import xlsxwriter
from frappe.desk.utils import provide_binary_file
from frappe.utils import flt, now_datetime

from client_akivision.client_akivision.api.item_list import get_item_list_stock_context


def build_item_information_rows(item_codes):
	if isinstance(item_codes, str):
		item_codes = frappe.parse_json(item_codes)
	if not isinstance(item_codes, list) or not item_codes or any(not isinstance(code, str) or not code.strip() for code in item_codes):
		frappe.throw("请先选择需要导出的物料。")
	codes = list(dict.fromkeys(item_codes))
	if len(codes) > 2500:
		frappe.throw("单次最多导出 2500 个物料，请缩小选择范围。")
	frappe.has_permission("Item", "read", throw=True)
	frappe.has_permission("Item", "export", throw=True)
	fields = ["name", "item_name", "item_group", "disabled", "stock_uom", "safety_stock"]
	meta = frappe.get_meta("Item")
	readable = set(meta.get_permitted_fieldnames(user=frappe.session.user, permission_type="read"))
	if not set(fields[1:]).issubset(readable):
		frappe.throw("没有权限导出所需物料字段。", frappe.PermissionError)
	items = frappe.get_list("Item", filters={"name": ["in", codes]}, fields=fields, limit_page_length=0)
	by_code = {item.name: item for item in items}
	if set(codes) != set(by_code):
		frappe.throw("部分所选物料不存在或无查看权限，请重新选择。", frappe.PermissionError)
	context = {}
	for offset in range(0, len(codes), 100):
		context.update(get_item_list_stock_context(codes[offset:offset + 100])["items"])
	summary, details = [], []
	for code in codes:
		item = by_code[code]
		stock = context.get(code)
		if stock is None:
			frappe.throw("物料权限已变化，请刷新列表后重新导出。", frappe.PermissionError)
		warehouses = stock.get("warehouses", [])
		levels = {row["warehouse"]: row["warehouse_reorder_level"] for row in stock.get("reorder_levels", [])}
		balances = {row["warehouse"]: row["actual_qty"] for row in warehouses}
		summary.append([code, item.item_name, item.item_group, "停用" if item.disabled else "启用", item.stock_uom,
			flt(item.safety_stock), sum(flt(row["actual_qty"]) for row in warehouses)])
		for warehouse in sorted(set(balances) | set(levels)):
			details.append([code, item.item_name, warehouse, item.stock_uom, flt(balances.get(warehouse)), levels.get(warehouse)])
	return summary, details


@frappe.whitelist()
def download_item_information(item_codes):
	summary, details = build_item_information_rows(item_codes)
	exported_at = now_datetime()
	output = BytesIO()
	workbook = xlsxwriter.Workbook(output, {"constant_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
	header_format = workbook.add_format({"bold": True, "bg_color": "#E8EEF5"})
	for title, headers, rows in [
		("物料汇总", ["物料编码", "物料名称", "物料组", "状态", "单位", "安全库存", "实际库存合计"], summary),
		("仓库库存明细", ["物料编码", "物料名称", "仓库", "单位", "实际剩余库存", "仓库补货预警线"], details),
	]:
		sheet = workbook.add_worksheet(title)
		sheet.write_row(0, 0, ["导出时间", exported_at.strftime("%Y-%m-%d %H:%M:%S")])
		sheet.write(1, 0, "口径：当前用户可见仓库的实际库存；未扣预留；空白预警线表示未配置。")
		sheet.write_row(3, 0, headers, header_format)
		for index, row in enumerate(rows, 4):
			sheet.write_row(index, 0, row)
		sheet.freeze_panes(4, 0)
		sheet.autofilter(3, 0, max(3, len(rows) + 3), len(headers) - 1)
		sheet.set_column(0, len(headers) - 1, 22)
	workbook.close()
	provide_binary_file(f"物料信息-{exported_at:%Y%m%d%H%M%S}", "xlsx", output.getvalue())
