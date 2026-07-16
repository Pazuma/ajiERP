import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("出库单号 / 物料编码"),
			"fieldname": "name",
			"fieldtype": "Data",
			"width": 200,
		},
		{"label": _("出库日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("出库类型"), "fieldname": "stock_entry_type", "fieldtype": "Data", "width": 120},
		{"label": _("操作员"), "fieldname": "owner", "fieldtype": "Data", "width": 100},
		{
			"label": _("物料编码"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": _("物料名称"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("版本"), "fieldname": "version", "fieldtype": "Data", "width": 80},
		{"label": _("适用机种"), "fieldname": "internal_model", "fieldtype": "Data", "width": 100},
		{
			"label": _("物料类别"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 100,
		},
		{"label": _("出库数量"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("应出库"), "fieldname": "expected_qty", "fieldtype": "Float", "width": 90},
		{
			"label": _("库位"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 120,
		},
		{"label": _("单价"), "fieldname": "basic_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("出库金额"), "fieldname": "basic_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("机种"), "fieldname": "model", "fieldtype": "Data", "width": 100},
		{"label": _("备注"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
		{"label": _("出库类别"), "fieldname": "issue_category", "fieldtype": "Data", "width": 120},
		{"label": _("说明"), "fieldname": "explanation", "fieldtype": "Data", "width": 200},
		{
			"label": _("出库单号"),
			"fieldname": "stock_entry",
			"fieldtype": "Link",
			"options": "Stock Entry",
			"width": 160,
		},
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
	conditions = get_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			sedi.name AS sed_name,
			sedi.item_code,
			sedi.item_name,
			sedi.qty,
			sedi.transfer_qty,
			sedi.basic_rate,
			sedi.basic_amount,
			sedi.s_warehouse AS warehouse,
			sedi.description AS item_description,
			sedi.idx AS item_idx,
			se.name AS stock_entry,
			se.posting_date,
			se.stock_entry_type,
			se.purpose,
			se.owner,
			se.remarks
		FROM `tabStock Entry Detail` sedi
		INNER JOIN `tabStock Entry` se ON se.name = sedi.parent
		WHERE se.docstatus = 1
		  AND sedi.s_warehouse IS NOT NULL
		  AND se.purpose != 'Material Receipt'
		  -- A transfer is not inherently an outbound transaction. Only the
		  -- dedicated customer sample-loan-out movement belongs in this list.
		  AND (
			se.purpose != 'Material Transfer'
			OR se.stock_entry_type = 'Sample Loan Out'
		  )
		  {conditions}
		ORDER BY se.posting_date DESC, se.name DESC, sedi.idx
		""",
		filters,
		as_dict=True,
	)

	if not rows:
		return []

	item_codes = list({row.item_code for row in rows})
	stock_entry_names = list({row.stock_entry for row in rows})
	sed_names = [row.sed_name for row in rows]

	item_fields = ["name", "item_group", "custom_internal_model"]
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

	# Stock Entry 级自定义字段
	se_fields = ["name"]
	se_field_map = {}
	for target, source in [
		("issue_category", "custom_issue_category"),
		("model", "custom_model"),
		("explanation", "custom_explanation"),
		("expected_qty", "custom_expected_qty"),
	]:
		if frappe.get_meta("Stock Entry").has_field(source):
			se_fields.append(source)
			se_field_map[target] = source

	se_details = {}
	if len(se_fields) > 1:
		se_details = {
			row.name: row
			for row in frappe.get_all(
				"Stock Entry",
				filters={"name": ["in", stock_entry_names]},
				fields=se_fields,
			)
		}

	# Stock Entry Detail 级自定义字段（优先级高于 SE 级）
	sed_fields = ["name"]
	sed_field_map = {}
	for target, source in [
		("model", "custom_model"),
		("expected_qty", "custom_expected_qty"),
	]:
		if frappe.get_meta("Stock Entry Detail").has_field(source):
			sed_fields.append(source)
			sed_field_map[target] = source

	sed_details = {}
	if len(sed_fields) > 1:
		sed_details = {
			row.name: row
			for row in frappe.get_all(
				"Stock Entry Detail",
				filters={"name": ["in", sed_names]},
				fields=sed_fields,
			)
		}

	purpose_label_map = {
		"Material Issue": _("物料发放"),
		"Material Transfer": _("物料调拨"),
		"Material Transfer for Manufacture": _("生产领料"),
		"Manufacture": _("生产制造"),
		"Repack": _("重新包装"),
		"Send to Subcontractor": _("外发加工"),
		"Material Consumption for Manufacture": _("生产消耗"),
	}

	# 按出库单汇总数量、金额
	aggregates = {}
	for row in rows:
		agg = aggregates.setdefault(row.stock_entry, {"qty": 0.0, "basic_amount": 0.0})
		agg["qty"] += flt(row.qty)
		agg["basic_amount"] += flt(row.basic_amount)

	data = []
	current_stock_entry = None
	for row in rows:
		se_extra = se_details.get(row.stock_entry, {})
		stock_entry_type_label = get_stock_entry_type_label(
			row.stock_entry_type, row.purpose
		)
		raw_issue_category = se_extra.get(se_field_map.get("issue_category"))
		issue_category_label = (
			get_stock_entry_type_label(raw_issue_category, row.purpose)
			if raw_issue_category
			else stock_entry_type_label
		)

		if row.stock_entry != current_stock_entry:
			current_stock_entry = row.stock_entry
			agg = aggregates[row.stock_entry]
			data.append(
				{
					"name": row.stock_entry,
					"parent": None,
					"indent": 0,
					"is_group": 1,
					"posting_date": row.posting_date,
					"stock_entry_type": stock_entry_type_label,
					"owner": row.owner,
					"remarks": row.remarks,
					"qty": agg["qty"],
					"basic_amount": agg["basic_amount"],
					"stock_entry": row.stock_entry,
					"issue_category": issue_category_label,
					"explanation": se_extra.get(se_field_map.get("explanation")) or "",
				}
			)

		item = item_details.get(row.item_code, {})
		sed_extra = sed_details.get(row.sed_name, {})

		expected_qty = sed_extra.get(sed_field_map.get("expected_qty")) or se_extra.get(
			se_field_map.get("expected_qty")
		)
		model = sed_extra.get(sed_field_map.get("model")) or se_extra.get(
			se_field_map.get("model")
		)
		explanation = se_extra.get(se_field_map.get("explanation")) or ""

		data.append(
			{
				"name": f"{row.stock_entry}#{row.item_idx}",
				"parent": row.stock_entry,
				"indent": 1,
				"is_group": 0,
				"name_display": row.item_code,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"version": item.get("custom_version") or "",
				"internal_model": item.get("custom_internal_model") or "",
				"item_group": item.get("item_group") or "",
				"qty": flt(row.qty),
				"expected_qty": flt(expected_qty) if expected_qty is not None else None,
				"posting_date": row.posting_date,
				"stock_entry": row.stock_entry,
				"stock_entry_type": stock_entry_type_label,
				"warehouse": row.warehouse,
				"basic_rate": flt(row.basic_rate),
				"basic_amount": flt(row.basic_amount),
				"owner": row.owner,
				"model": model or "",
				"remarks": row.remarks or row.item_description or "",
				"issue_category": issue_category_label,
				"explanation": explanation,
			}
		)

	return data


def get_conditions(filters):
	conditions = []
	if filters.get("company"):
		conditions.append("AND se.company = %(company)s")
	if filters.get("stock_entry_type"):
		conditions.append("AND se.stock_entry_type = %(stock_entry_type)s")
	if filters.get("from_date"):
		conditions.append("AND se.posting_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("AND se.posting_date <= %(to_date)s")
	if filters.get("item_code"):
		conditions.append("AND sedi.item_code = %(item_code)s")
	if filters.get("warehouse"):
		conditions.append("AND sedi.s_warehouse = %(warehouse)s")
	return " ".join(conditions)
