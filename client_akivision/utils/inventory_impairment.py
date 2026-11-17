"""Inventory impairment configuration and reminder helpers for aki_test."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import add_months, cint, date_diff, flt, getdate, now_datetime, today


ITEM_FIELDS = [
	{"fieldname": "custom_inventory_impairment_items", "label": "折旧物料表", "fieldtype": "Table", "options": "Inventory Impairment Item", "insert_after": "custom_inventory_impairment_protection_months"},
	{"fieldname": "custom_inventory_impairment_enabled", "label": "参与库存减值评估", "fieldtype": "Check", "insert_after": "is_stock_item", "default": "0"},
	{"fieldname": "custom_inventory_impairment_rule", "label": "库存减值规则", "fieldtype": "Data", "insert_after": "custom_inventory_impairment_enabled"},
	{"fieldname": "custom_inventory_impairment_max_ratio", "label": "最大累计减值比例", "fieldtype": "Percent", "insert_after": "custom_inventory_impairment_rule"},
	{"fieldname": "custom_inventory_impairment_reversal_allowed", "label": "允许转回", "fieldtype": "Check", "insert_after": "custom_inventory_impairment_max_ratio", "default": "1"},
	{"fieldname": "custom_inventory_impairment_protection_months", "label": "恢复保护期（月）", "fieldtype": "Int", "insert_after": "custom_inventory_impairment_reversal_allowed"},
]


def ensure_schema():
	"""Create optional Item fields; existing inventory valuation remains untouched."""
	if not frappe.db.exists("DocType", "Item"):
		return
	for field in ITEM_FIELDS:
		if not frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": field["fieldname"]}):
			create_custom_field("Item", field)
	frappe.clear_cache(doctype="Item")


@frappe.whitelist()
def get_item_reminder(item_code=None):
	"""Return configuration summary used by the Item page; calculation is advisory only."""
	if not item_code:
		frappe.throw("item_code is required")
	item = frappe.db.get_value("Item", item_code, [f["fieldname"] for f in ITEM_FIELDS], as_dict=True)
	if not item:
		frappe.throw("Item not found")
	return {"enabled": item.custom_inventory_impairment_enabled, "rule": item.custom_inventory_impairment_rule, "max_ratio": item.custom_inventory_impairment_max_ratio, "reversal_allowed": item.custom_inventory_impairment_reversal_allowed, "protection_months": item.custom_inventory_impairment_protection_months}


def calculate_assessment(row, assessment_date, qty):
	"""Full calendar periods after grace; additive percentage of original value."""
	if not row.get("start_date") or not row.get("warehouse"):
		frappe.throw("自动减值评估必须填写仓库和减值起算日期")
	period = cint(row.get("period_months"))
	unit = row.get("period_unit") or "月"
	grace = cint(row.get("grace_months"))
	rate = flt(row.get("basis_rate"))
	ratio = flt(row.get("period_ratio"))
	cap = flt(row.get("max_ratio"))
	if unit not in ("年", "月", "日") or period < 1 or grace < 0 or rate <= 0 or not 0 < ratio <= 100 or not 0 < cap <= 100:
		frappe.throw("周期须为至少1的年、月或日，免减值月数不得为负；原始单价须大于0，比例及上限须大于0且不超过100%")
	start, end = getdate(row.get("start_date")), getdate(assessment_date)
	months = max(0, (end.year - start.year) * 12 + end.month - start.month)
	# Compare anniversaries against the original date, including month ends.
	if getdate(add_months(start, months)) > end:
		months = max(0, months - 1)
	if unit == "日":
		steps = max(0, date_diff(end, add_months(start, grace))) // period
	else:
		# A missing unit is a legacy month rule; retain its exact calendar boundaries.
		steps = max(0, months - grace) // (period * (12 if unit == "年" else 1))
	accumulated = min(cap, steps * ratio)
	return {
		"assessment_date": end,
		"stock_qty": max(0, flt(qty)),
		"impairment_ratio": accumulated,
		"reference_rate": flt(rate * (1 - accumulated / 100), 6),
		"impairment_amount": flt(max(0, flt(qty)) * rate * accumulated / 100, 2),
	}


@frappe.whitelist()
def get_item_usage_times(item_code):
	"""Read-only system usage timestamps for the current Item's permitted warehouses."""
	if not isinstance(item_code, str) or not item_code:
		frappe.throw("请选择已保存的物料")
	doc = frappe.get_doc("Item", item_code)
	doc.check_permission("read")
	if not all(frappe.has_permission(dt, "read") for dt in ("Company", "Warehouse")):
		return {}
	# Import locally: the summary service also reuses calculate_assessment.
	from client_akivision.utils.inventory_impairment_summary import get_last_effective_usage
	companies = frappe.get_list("Company", pluck="name", limit_page_length=0)
	if not companies:
		return {}
	warehouses = set(frappe.get_list("Warehouse", filters={"company": ["in", companies],
		"disabled": 0, "is_group": 0}, pluck="name", limit_page_length=0))
	pairs = {(item_code, row.warehouse) for row in doc.get("custom_inventory_impairment_items") or []
		if row.warehouse in warehouses}
	usage = get_last_effective_usage(pairs, now_datetime())
	return {warehouse: row.posting_datetime for (_, warehouse), row in usage.items()}


def assess_item(doc, method=None):
	"""Only explicitly enabled rows are calculated; legacy/manual rows stay intact."""
	seen = set()
	for row in doc.get("custom_inventory_impairment_items") or []:
		if not row.get("auto_assess"):
			continue
		if row.warehouse in seen:
			frappe.throw("同一物料同一仓库只允许一条自动减值规则，避免重复汇总")
		seen.add(row.warehouse)
		# Posted accounting records must not be silently overwritten by estimates.
		if row.status in ("已计提", "已转回", "建议转回"):
			frappe.throw("已计提或转回的明细不能启用自动评估，请保留原记录并停用其自动评估")
		qty = frappe.db.get_value("Bin", {"item_code": doc.name, "warehouse": row.warehouse}, "actual_qty") or 0
		row.update(calculate_assessment(row, today(), qty))
		row.status = "已评估（未计提）"


def scheduled_assess_items():
	"""Daily advisory refresh, with one transaction savepoint per Item."""
	items = frappe.get_all("Inventory Impairment Item", filters={
		"auto_assess": 1, "parenttype": "Item", "parentfield": "custom_inventory_impairment_items",
	}, pluck="parent")
	for item_code in sorted(set(items)):
		frappe.db.savepoint("inventory_impairment_item")
		try:
			doc = frappe.get_doc("Item", item_code)
			if doc.disabled:
				continue
			assess_item(doc)
			for row in doc.custom_inventory_impairment_items:
				if row.auto_assess:
					row.db_update()
		except Exception:
			frappe.db.rollback(save_point="inventory_impairment_item")
			frappe.log_error(title=f"库存减值自动评估失败: {item_code}", message=frappe.get_traceback())
