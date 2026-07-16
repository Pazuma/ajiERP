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

	return get_columns(), frappe.db.sql(query, filters)


def get_columns():
	return [
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
