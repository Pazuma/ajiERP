import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data), 1


def get_report_summary(data):
	status_count = {"Below Safety": 0, "Warning": 0, "Over Max": 0}
	for row in data:
		status = str(row.status)
		if status in {"Below Safety", _("Below Safety")}:
			status_count["Below Safety"] += 1
		elif status in {"Warning", _("Warning")}:
			status_count["Warning"] += 1
		elif status in {"Over Max", _("Over Max")}:
			status_count["Over Max"] += 1

	return [
		{"value": len(data), "label": _("受监控物料"), "datatype": "Int", "indicator": "Blue"},
		{"value": status_count.get("Below Safety", 0), "label": _("低于安全库存"), "datatype": "Int", "indicator": "Red"},
		{"value": status_count.get("Warning", 0), "label": _("预警"), "datatype": "Int", "indicator": "Orange"},
		{"value": status_count.get("Over Max", 0), "label": _("超过上限"), "datatype": "Int", "indicator": "Red"},
	]


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{
			"label": _("Item Type"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 120,
		},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 140,
		},
		{"label": _("Actual Qty"), "fieldname": "actual_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Projected Qty"), "fieldname": "projected_qty", "fieldtype": "Float", "width": 165},
		{"label": _("Minimum Safety Stock"), "fieldname": "safety_stock", "fieldtype": "Float", "width": 120},
		{"label": _("Warning Line"), "fieldname": "reorder_level", "fieldtype": "Float", "width": 110},
		{"label": _("Max Stock Limit"), "fieldname": "max_stock_limit", "fieldtype": "Float", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		SELECT
			i.name AS item_code,
			i.item_name,
			i.item_group,
			i.safety_stock,
			i.custom_safety_stock_remarks AS remarks,
			ir.warehouse,
			ir.warehouse_reorder_level AS reorder_level,
			ir.custom_max_stock_limit AS max_stock_limit,
			b.actual_qty,
			b.projected_qty
		FROM `tabItem` i
		INNER JOIN `tabItem Reorder` ir ON ir.parent = i.name
		LEFT JOIN `tabBin` b ON b.item_code = i.name AND b.warehouse = ir.warehouse
		WHERE i.disabled = 0
		  AND i.is_stock_item = 1
		  AND (ir.warehouse_reorder_level > 0 OR ir.custom_max_stock_limit > 0 OR i.safety_stock > 0)
		  {conditions}
		ORDER BY i.name, ir.warehouse
		""",
		filters,
		as_dict=True,
	)

	for row in rows:
		row.actual_qty = flt(row.actual_qty)
		row.projected_qty = flt(row.projected_qty)
		row.safety_stock = flt(row.safety_stock)
		row.reorder_level = flt(row.reorder_level)
		row.max_stock_limit = flt(row.max_stock_limit)
		row.status = get_status(row)

	if filters.get("status"):
		selected_status = {
			"Normal": _("Normal"),
			"Warning": _("Warning"),
			"Below Safety": _("Below Safety"),
			"Over Max": _("Over Max"),
		}.get(filters.status, filters.status)
		rows = [row for row in rows if row.status == selected_status]

	return rows


def get_status(row):
	projected = row.projected_qty
	if row.max_stock_limit and projected > row.max_stock_limit:
		return _("Over Max")
	if row.safety_stock and projected <= row.safety_stock:
		return _("Below Safety")
	if row.reorder_level and projected <= row.reorder_level:
		return _("Warning")
	return _("Normal")


def get_conditions(filters):
	conditions = []
	if filters.get("company"):
		conditions.append("AND EXISTS (SELECT 1 FROM `tabWarehouse` w WHERE w.name = ir.warehouse AND w.company = %(company)s)")
	if filters.get("warehouse"):
		conditions.append("AND ir.warehouse = %(warehouse)s")
	if filters.get("item_group"):
		conditions.append("AND i.item_group = %(item_group)s")
	return " ".join(conditions)
