import frappe
from frappe import _
from client_akivision.utils.department_inventory import format_stock_rows, get_configured_list, get_stock_rows, require_scope


def execute(filters=None):
	filters = frappe._dict(filters or {})
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("请先选择公司"))
	warehouses = require_scope("finished_goods_inventory_warehouses", company)
	groups = get_configured_list("finished_goods_inventory_item_groups")
	rows = [row for group in groups for row in get_stock_rows(warehouses, company, group)] if groups else get_stock_rows(warehouses, company)
	return get_columns(), format_stock_rows(rows)


def get_columns():
	return [
		{"label": "成品编码", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "成品名称", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
		{"label": "物料组", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 120},
		{"label": "实际库存", "fieldname": "actual_qty", "fieldtype": "Float", "width": 110},
		{"label": "预计可用", "fieldname": "projected_qty", "fieldtype": "Float", "width": 110},
		{"label": "单位", "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
		{"label": "成品仓", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
	]

