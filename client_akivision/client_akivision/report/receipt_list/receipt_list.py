import frappe
from frappe import _
from frappe.utils import flt
from functools import cmp_to_key


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Delivery Note No / Item Code"),
			"fieldname": "name",
			"fieldtype": "Data",
			"width": 200,
		},
		{"label": _("入库日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("入库类型"), "fieldname": "receipt_type", "fieldtype": "Data", "width": 100},
		{
			"label": _("供应商"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 130,
		},
		{
			"label": _("采购单号"),
			"fieldname": "purchase_order",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 130,
		},
		{
			"label": _("物料编码"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("版本"), "fieldname": "version", "fieldtype": "Data", "width": 80},
		{"label": _("适用机种"), "fieldname": "applicable_model", "fieldtype": "Data", "width": 100},
		{
			"label": _("物料类别"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100,
		},
		{"label": _("入库数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{
			"label": _("库位"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{"label": _("单价"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
		{"label": _("总价"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("操作员"), "fieldname": "owner", "fieldtype": "Data", "width": 100},
		{
			"label": _("镜片入库单/退料单"),
			"fieldname": "receipt_name",
			"fieldtype": "Dynamic Link",
			"options": "doc_doctype",
			"width": 170,
		},
		{"label": _("对帐日期"), "fieldname": "reconciliation_date", "fieldtype": "Date", "width": 110},
		{"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
	]


def get_stock_entry_type_label(stock_entry_type, purpose):
	type_label_map = {
		"Material Issue": _("物料发放"),
		"Material Receipt": _("物料接收"),
		"Material Transfer": _("物料调拨"),
		"Material Transfer for Manufacture": _("生产领料"),
		"Manufacture": _("生产制造"),
		"Repack": _("重新包装"),
		"Send to Subcontractor": _("外发加工"),
		"Material Consumption for Manufacture": _("生产消耗"),
	}
	if stock_entry_type:
		return type_label_map.get(stock_entry_type) or _(stock_entry_type)
	return type_label_map.get(purpose) or _(purpose) or purpose


def get_data(filters):
	pr_items = get_purchase_receipt_items(filters)
	se_items = get_stock_entry_items(filters)
	all_items = pr_items + se_items

	if not all_items:
		return []

	# 按日期降序、单号降序、行号升序排列
	all_items.sort(
		key=cmp_to_key(
			lambda a, b: (
				-1
				if a.posting_date > b.posting_date
				else 1 if a.posting_date < b.posting_date else (
					-1
					if a.doc_name > b.doc_name
					else 1 if a.doc_name < b.doc_name else a.item_idx - b.item_idx
				)
			)
		)
	)

	item_codes = list({row.item_code for row in all_items})
	pr_names = list({row.doc_name for row in pr_items})

	item_fields = ["name", "item_group"]
	if frappe.get_meta("Item").has_field("custom_applicable_model"):
		item_fields.append("custom_applicable_model")
	if frappe.get_meta("Item").has_field("custom_version"):
		item_fields.append("custom_version")

	item_details = {
		row.name: row
		for row in frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=item_fields,
		)
	}

	receipt_fields = ["name"]
	if frappe.get_meta("Purchase Receipt").has_field("custom_reconciliation_date"):
		receipt_fields.append("custom_reconciliation_date")
	if frappe.get_meta("Purchase Receipt").has_field("custom_lens_receipt_no"):
		receipt_fields.append("custom_lens_receipt_no")

	receipt_details = {}
	if len(receipt_fields) > 1:
		receipt_details = {
			row.name: row
			for row in frappe.get_all(
				"Purchase Receipt",
				filters={"name": ["in", pr_names]},
				fields=receipt_fields,
			)
		}

	# 按单据汇总数量、金额
	aggregates = {}
	for row in all_items:
		agg = aggregates.setdefault(
			(row.doc_doctype, row.doc_name), {"qty": 0.0, "amount": 0.0}
		)
		agg["qty"] += flt(row.qty)
		agg["amount"] += flt(row.amount)

	data = []
	current_doc = None
	for row in all_items:
		doc_key = (row.doc_doctype, row.doc_name)
		is_pr = row.doc_doctype == "Purchase Receipt"
		receipt = receipt_details.get(row.doc_name, {}) if is_pr else {}

		if doc_key != current_doc:
			current_doc = doc_key
			agg = aggregates[doc_key]
			parent_row = {
				"name": f"{row.doc_doctype}-{row.doc_name}",
				"parent": None,
				"indent": 0,
				"is_group": 1,
				"name_display": row.doc_name,
				"posting_date": row.posting_date,
				"receipt_type": row.doc_type_label,
				"supplier": row.supplier,
				"qty": agg["qty"],
				"amount": agg["amount"],
				"owner": row.owner,
				"remarks": row.remarks,
				"doc_doctype": row.doc_doctype,
			}
			if is_pr:
				parent_row["receipt_name"] = (
					receipt.get("custom_lens_receipt_no") or row.doc_name
				)
				parent_row["reconciliation_date"] = receipt.get(
					"custom_reconciliation_date"
				)
			data.append(parent_row)

		item = item_details.get(row.item_code, {})
		child_row = {
			"name": f"{row.doc_doctype}-{row.doc_name}#{row.item_idx}",
			"parent": f"{row.doc_doctype}-{row.doc_name}",
			"indent": 1,
			"is_group": 0,
			"name_display": row.item_code,
			"item_code": row.item_code,
			"item_name": row.item_name,
			"version": item.get("custom_version") or "",
			"applicable_model": item.get("custom_applicable_model") or "",
			"item_group": item.get("item_group") or "",
			"qty": flt(row.qty),
			"warehouse": row.warehouse,
			"purchase_order": row.purchase_order,
			"rate": flt(row.rate),
			"amount": flt(row.amount),
			"owner": row.owner,
			"remarks": row.remarks or "",
			"doc_doctype": row.doc_doctype,
		}
		if is_pr:
			child_row["receipt_name"] = receipt.get("custom_lens_receipt_no") or row.doc_name
			child_row["reconciliation_date"] = receipt.get("custom_reconciliation_date")
		data.append(child_row)

	return data


def get_purchase_receipt_items(filters):
	conditions = get_pr_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			pri.item_code,
			pri.item_name,
			pri.qty,
			pri.warehouse,
			pri.rate,
			pri.amount,
			pri.purchase_order,
			pri.idx AS item_idx,
			pr.name AS doc_name,
			pr.posting_date,
			pr.is_return,
			pr.supplier,
			pr.owner,
			pr.remarks
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
		WHERE pr.docstatus = 1 {conditions}
		ORDER BY pr.posting_date DESC, pr.name DESC, pri.idx
		""",
		filters,
		as_dict=True,
	)
	for row in rows:
		row.doc_doctype = "Purchase Receipt"
		row.doc_type_label = _("退料单") if row.is_return else _("采购入库")
	return rows


def get_stock_entry_items(filters):
	conditions = get_se_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			sedi.item_code,
			sedi.item_name,
			sedi.qty,
			sedi.t_warehouse AS warehouse,
			sedi.basic_rate AS rate,
			sedi.basic_amount AS amount,
			NULL AS purchase_order,
			sedi.idx AS item_idx,
			se.name AS doc_name,
			se.posting_date,
			se.stock_entry_type,
			se.purpose,
			se.owner,
			se.remarks
		FROM `tabStock Entry Detail` sedi
		INNER JOIN `tabStock Entry` se ON se.name = sedi.parent
		WHERE se.docstatus = 1
		  AND sedi.t_warehouse IS NOT NULL
		  -- A transfer is not inherently a receipt. Include only the
		  -- customer sample-loan return movement that actually returns stock.
		  AND (
			se.purpose = 'Material Receipt'
			OR se.stock_entry_type = 'Sample Loan Out Return'
		  )
		  {conditions}
		ORDER BY se.posting_date DESC, se.name DESC, sedi.idx
		""",
		filters,
		as_dict=True,
	)
	for row in rows:
		row.doc_doctype = "Stock Entry"
		row.doc_type_label = get_stock_entry_type_label(row.stock_entry_type, row.purpose)
		row.supplier = ""
	return rows


def get_pr_conditions(filters):
	conditions = []
	if filters.get("company"):
		conditions.append("AND pr.company = %(company)s")
	if filters.get("supplier"):
		conditions.append("AND pr.supplier = %(supplier)s")
	if filters.get("from_date"):
		conditions.append("AND pr.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("AND pr.posting_date <= %(to_date)s")
	if filters.get("item_code"):
		conditions.append("AND pri.item_code = %(item_code)s")
	if filters.get("purchase_order"):
		conditions.append("AND pri.purchase_order = %(purchase_order)s")
	if filters.get("warehouse"):
		conditions.append("AND pri.warehouse = %(warehouse)s")
	return " ".join(conditions)


def get_se_conditions(filters):
	conditions = []
	if filters.get("company"):
		conditions.append("AND se.company = %(company)s")
	if filters.get("from_date"):
		conditions.append("AND se.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("AND se.posting_date <= %(to_date)s")
	if filters.get("item_code"):
		conditions.append("AND sedi.item_code = %(item_code)s")
	if filters.get("warehouse"):
		conditions.append("AND sedi.t_warehouse = %(warehouse)s")
	return " ".join(conditions)
