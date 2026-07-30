import frappe
from frappe import _


def execute(filters=None):
	"""Run the configured summary query with safe optional filter defaults."""
	filters = frappe._dict(filters or {})
	filters.company = filters.get("company") or frappe.defaults.get_user_default("Company") or ""
	filters.internal_model = filters.get("internal_model") or ""
	filters.external_model = filters.get("external_model") or ""

	query = frappe.db.get_value("Report", "Summary Calculation", "query")
	if not query:
		frappe.throw(_("汇总计算报表查询尚未配置"))
	# Keep the report query configurable while adding stable item identity and
	# sample-warehouse stock semantics for older saved queries.
	query = query.replace(
		"SELECT\n    i.custom_internal_model",
		"SELECT\n    i.name AS `物料编码:Data:140`,\n    i.item_name AS `物料名称:Data:180`,\n    i.custom_internal_model",
		1,
	)
	query = query.replace("COALESCE(fgs.sample_qty, 0)", "COALESCE(sample_stock.sample_qty, 0)")
	query = query.replace(
		"WHERE (COALESCE(%(company)s, '') = '' OR stock_warehouse.company = %(company)s)\n    GROUP BY item_code\n) stock",
		"WHERE (COALESCE(%(company)s, '') = '' OR stock_warehouse.company = %(company)s)\n      AND stock_warehouse.name <> COALESCE((SELECT value FROM `tabSingles` WHERE doctype = 'Stock Settings' AND field = 'sample_retention_warehouse'), '')\n    GROUP BY item_code\n) stock",
		1,
	)
	query = query.replace(
		"FROM `tabItem` i\nLEFT JOIN (",
		"FROM `tabItem` i\nLEFT JOIN (\n    SELECT b.item_code, SUM(b.actual_qty) AS sample_qty\n    FROM `tabBin` b\n    INNER JOIN `tabWarehouse` sw ON sw.name = b.warehouse\n    INNER JOIN (SELECT value AS sample_warehouse FROM `tabSingles` WHERE doctype = 'Stock Settings' AND field = 'sample_retention_warehouse') ss ON 1=1\n    WHERE sw.name = ss.sample_warehouse\n      AND (COALESCE(%(company)s, '') = '' OR sw.company = %(company)s)\n    GROUP BY b.item_code\n) sample_stock ON sample_stock.item_code = i.name\nLEFT JOIN (",
		1,
	)

	return get_columns(), frappe.db.sql(query, filters)


def get_columns():
	return [
		{"label": _("物料编码"), "fieldname": "item_code", "fieldtype": "Data", "width": 140},
		{"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("内部机种"), "fieldname": "internal_model", "fieldtype": "Data", "width": 120},
		{"label": _("外部型号"), "fieldname": "external_model", "fieldtype": "Data", "width": 180},
		{"label": _("销售品"), "fieldname": "sold_qty", "fieldtype": "Int", "width": 90},
		{"label": _("库存品"), "fieldname": "stock_qty", "fieldtype": "Float", "width": 90},
		{"label": _("样品"), "fieldname": "sample_qty", "fieldtype": "Int", "width": 80},
		{"label": _("借出样品"), "fieldname": "loan_out_qty", "fieldtype": "Float", "width": 100},
		{"label": _("借回样品"), "fieldname": "loan_in_qty", "fieldtype": "Float", "width": 100},
		{"label": _("在制品"), "fieldname": "wip_qty", "fieldtype": "Float", "width": 90},
		{"label": _("总计数量"), "fieldname": "total_qty", "fieldtype": "Float", "width": 100},
		{"label": _("状态"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
	]
