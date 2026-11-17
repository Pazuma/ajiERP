import frappe


def execute(filters=None):
	columns = [
		{"label": "物料", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "物料名称", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "仓库", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 160},
		{"label": "减值起算日期", "fieldname": "start_date", "fieldtype": "Date", "width": 110},
		{"label": "原始参考单价", "fieldname": "basis_rate", "fieldtype": "Currency", "width": 120},
		{"label": "当前库存数量", "fieldname": "stock_qty", "fieldtype": "Float", "width": 110},
		{"label": "减值后参考单价", "fieldname": "reference_rate", "fieldtype": "Currency", "width": 130},
		{"label": "最后有效使用日期", "fieldname": "last_activity_date", "fieldtype": "Date", "width": 130},
		{"label": "评估日期", "fieldname": "assessment_date", "fieldtype": "Date", "width": 110},
		{"label": "累计减值比例", "fieldname": "impairment_ratio", "fieldtype": "Percent", "width": 110},
		{"label": "跌价准备建议金额", "fieldname": "impairment_amount", "fieldtype": "Currency", "width": 140},
		{"label": "状态", "fieldname": "status", "fieldtype": "Data", "width": 100},
	]
	data = frappe.db.sql("""
		select p.parent item_code, i.item_name, p.warehouse, p.last_activity_date,
		p.assessment_date, p.impairment_ratio, p.impairment_amount, p.status,
		p.start_date, p.basis_rate, p.stock_qty, p.reference_rate
		from `tabInventory Impairment Item` p
		join `tabItem` i on i.name = p.parent
		where ifnull(p.impairment_amount, 0) > 0
		order by p.assessment_date desc, p.parent
	""", as_dict=True)
	return columns, data
