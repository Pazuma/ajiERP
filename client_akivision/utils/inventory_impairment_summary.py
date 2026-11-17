"""Read-only current-day view of existing Item impairment rules."""

from collections import Counter, defaultdict
from html import escape
import math

import frappe
from frappe.utils import cint, date_diff, flt, getdate, now_datetime, today

from client_akivision.utils.inventory_impairment import calculate_assessment


REPORT_NAME = "物料折旧汇总"
PROTECTED_STATUSES = {"已计提", "已转回", "建议转回"}
CHUNK_SIZE = 200


def _chunks(values):
	values = list(values)
	for offset in range(0, len(values), CHUNK_SIZE):
		yield values[offset:offset + CHUNK_SIZE]


def _check_access():
	if not {"Stock Manager", "Accounts Manager", "Administrator"}.intersection(frappe.get_roles()):
		frappe.throw("无权访问物料折旧汇总", frappe.PermissionError)
	for doctype in ("Item", "Warehouse", "Company"):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw("无权读取物料、仓库或公司", frappe.PermissionError)
	if not frappe.has_permission("Item", "report"):
		frappe.throw("无权读取物料报表", frappe.PermissionError)


def _filters(values):
	values = frappe._dict(values or {})
	if set(values) - {"company", "warehouse", "item_code", "only_in_stock", "min_idle_days"}:
		frappe.throw("物料折旧汇总仅支持今日视图及页面列出的筛选条件")
	for field in ("company", "warehouse", "item_code"):
		if values.get(field) is not None and not isinstance(values[field], str):
			frappe.throw("筛选条件格式不正确")
	if values.get("min_idle_days") not in (None, ""):
		try:
			days = float(values.min_idle_days)
			if not math.isfinite(days) or days < 0 or not days.is_integer():
				raise ValueError
		except (TypeError, ValueError, OverflowError):
			frappe.throw("未使用天数须为非负整数")
		values.min_idle_days = int(days)
	else:
		values.min_idle_days = None
	if values.get("only_in_stock") not in (None, "", 0, 1, "0", "1"):
		frappe.throw("仅有库存筛选格式不正确")
	values.only_in_stock = cint(values.get("only_in_stock", 1))
	return values


def _allowed(doctype, fields, selected=None, extra_filters=None):
	filters = dict(extra_filters or {})
	if selected:
		filters["name"] = selected
	# get_list, unlike get_all/raw SQL, applies match conditions and User Permissions.
	rows = frappe.get_list(doctype, fields=fields, filters=filters, limit_page_length=0)
	if selected and not rows:
		frappe.throw("筛选项不存在或无权读取", frappe.PermissionError)
	return {row.name: row for row in rows}


def _load_candidates(filters):
	companies = _allowed("Company", ["name", "default_currency"], filters.company)
	warehouses = _allowed("Warehouse", ["name", "company", "disabled", "is_group"], filters.warehouse)
	warehouses = {key: row for key, row in warehouses.items() if row.company in companies}
	if filters.warehouse and filters.warehouse not in warehouses:
		frappe.throw("筛选仓库不属于可读取的公司", frappe.PermissionError)
	items = _allowed("Item", ["name", "item_name", "stock_uom", "disabled", "is_stock_item"], filters.item_code)
	rules = []
	for names in _chunks(items):
		rules.extend(frappe.get_all("Inventory Impairment Item", filters={
			"parenttype": "Item", "parentfield": "custom_inventory_impairment_items",
			"parent": ["in", names], "auto_assess": 1,
		}, fields=["name", "parent", "warehouse", "start_date", "grace_months", "period_months",
			"period_unit", "period_ratio", "max_ratio", "basis_rate", "status", "assessment_date"], limit_page_length=0))
	# Never disclose rule details for a warehouse outside the permitted set.
	rules = [row for row in rules if not row.warehouse or row.warehouse in warehouses]
	bins = {}
	for names in _chunks({row.parent for row in rules}):
		if not warehouses:
			break
		for row in frappe.get_all("Bin", filters={"item_code": ["in", names], "warehouse": ["in", list(warehouses)]},
			fields=["item_code", "warehouse", "actual_qty", "valuation_rate", "stock_value"], limit_page_length=0):
			bins[(row.item_code, row.warehouse)] = row
	return items, warehouses, companies, rules, bins


def _evaluate(rules, items, warehouses, companies, bins, filters, assessment_date):
	counts = Counter((row.parent, row.warehouse) for row in rules)
	rows, issues = [], []
	for rule in rules:
		item, warehouse = items[rule.parent], warehouses.get(rule.warehouse)
		reason = None
		if item.disabled or not item.is_stock_item:
			reason = "物料已停用或不是库存物料"
		elif not warehouse or warehouse.disabled or warehouse.is_group:
			reason = "仓库为空、已停用或不是明细仓库"
		elif counts[(rule.parent, rule.warehouse)] > 1:
			reason = "同一仓库存在多条启用规则，请回物料修正"
		elif rule.status in PROTECTED_STATUSES:
			reason = "已计提或转回的历史记录不参与自动测算"
		stock = bins.get((rule.parent, rule.warehouse))
		if not reason and stock is None:
			reason = "缺少库存余额记录，请核对"
		if not reason and flt(stock.actual_qty) < 0:
			reason = "负库存，请核对后评估"
		if reason:
			issues.append((rule.parent, reason))
			continue
		try:
			previous_mute = frappe.flags.mute_messages
			try:
				frappe.flags.mute_messages = True
				assessment = calculate_assessment(rule, assessment_date, stock.actual_qty)
			finally:
				frappe.flags.mute_messages = previous_mute
		except (frappe.ValidationError, ValueError, TypeError, OverflowError):
			issues.append((rule.parent, "折旧规则无效，请核对日期、单价、周期及比例"))
			continue
		if assessment["impairment_ratio"] <= 0:
			continue
		if filters.only_in_stock and flt(stock.actual_qty) == 0:
			continue
		rows.append(frappe._dict(
			item_code=rule.parent, item_name=item.item_name, stock_uom=item.stock_uom,
			warehouse=rule.warehouse, company=warehouse.company,
			currency=companies[warehouse.company].default_currency,
			stock_qty=assessment["stock_qty"], valuation_rate=stock.valuation_rate,
			stock_value=stock.stock_value, basis_rate=rule.basis_rate, start_date=rule.start_date,
			period_label=f"每{cint(rule.period_months)}{rule.get('period_unit') or '月'}",
			period_ratio=rule.period_ratio,
			impairment_ratio=assessment["impairment_ratio"], reference_rate=assessment["reference_rate"],
			impairment_amount=assessment["impairment_amount"], calculation_date=assessment_date,
			saved_assessment_date=rule.assessment_date,
			status="无库存" if not flt(stock.actual_qty) else "已开始折旧（未计提）",
		))
	return rows, issues


def get_last_effective_usage(pairs, cutoff):
	"""Find latest genuine outflow, not transfers, returns, or valuation changes."""
	latest = {}
	sources = (
		("Delivery Note", "Delivery Note Item", "d.warehouse = sle.warehouse", ""),
		("Sales Invoice", "Sales Invoice Item", "d.warehouse = sle.warehouse", "and v.update_stock = 1"),
		("Stock Entry", "Stock Entry Detail", "d.s_warehouse = sle.warehouse and ifnull(d.is_finished_item, 0) = 0",
			"and v.purpose in ('Manufacture', 'Material Consumption for Manufacture')"),
	)
	for batch in _chunks(sorted(set(pairs))):
		pair_sql = " or ".join("(sle.item_code = %s and sle.warehouse = %s)" for _ in batch)
		for doctype, detail, detail_match, extra in sources:
			params = [doctype, cutoff, *[part for pair in batch for part in pair]]
			# All table identifiers/clauses come from the fixed source list, not filters.
			found = frappe.db.sql(f"""
				select item_code, warehouse, posting_datetime, voucher_type, voucher_no
				from (
					select sle.item_code, sle.warehouse, sle.posting_datetime, sle.voucher_type, sle.voucher_no,
					row_number() over (partition by sle.item_code, sle.warehouse
						order by sle.posting_datetime desc, sle.creation desc, sle.name desc) as rn
					from `tabStock Ledger Entry` sle
					inner join `tab{doctype}` v on v.name = sle.voucher_no
					inner join `tab{detail}` d on d.name = sle.voucher_detail_no and d.parent = v.name
						and d.parenttype = sle.voucher_type and d.parentfield = 'items'
						and d.item_code = sle.item_code and {detail_match}
					where sle.voucher_type = %s and sle.posting_datetime <= %s
						and ifnull(sle.is_cancelled, 0) = 0 and sle.actual_qty < 0
						and v.docstatus = 1 and ifnull(v.is_return, 0) = 0
						and ({pair_sql}) {extra}
				) usage_rows where rn = 1
			""", params, as_dict=True)
			for row in found:
				key = (row.item_code, row.warehouse)
				if key not in latest or row.posting_datetime > latest[key].posting_datetime:
					latest[key] = row
	return latest


def _visible_sources(usage):
	visible = set()
	by_type = defaultdict(set)
	for row in usage.values():
		by_type[row.voucher_type].add(row.voucher_no)
	for doctype, names in by_type.items():
		if not frappe.has_permission(doctype, "read"):
			continue
		for batch in _chunks(names):
			for row in frappe.get_list(doctype, filters={"name": ["in", batch]}, fields=["name"], limit_page_length=0):
				visible.add((doctype, row.name))
	return visible


def get_columns():
	definitions = [
		("物料", "item_code", "Link", 220, "Item"),
		("周期", "period_label", "Data", 110, None),
		("每周期减少（%）", "period_ratio", "Percent", 140, None),
		("最后使用时间", "last_usage_time", "Datetime", 190, None),
		("物料名称", "item_name", "Data", 160, None),
		("仓库", "warehouse", "Link", 170, "Warehouse"),
		("当前库存数量", "stock_qty", "Float", 110, None),
		("单位", "stock_uom", "Data", 70, None),
		("原始单价", "basis_rate", "Currency", 130, "currency"),
		("累计折旧比例", "impairment_ratio", "Percent", 110, None),
		("折旧后参考单价", "reference_rate", "Currency", 130, "currency"),
		("建议减值金额", "impairment_amount", "Currency", 130, "currency"),
		("最后有效使用日期", "last_activity_date", "Date", 135, None),
		("未使用天数", "idle_days", "Int", 100, None),
		("使用记录说明", "usage_status", "Data", 210, None),
		("最近保存评估日期", "saved_assessment_date", "Date", 135, None),
		("状态", "status", "Data", 180, None),
		("公司", "company", "Link", 170, "Company"),
		("币种", "currency", "Data", 70, None),
		("当前库存单价", "valuation_rate", "Currency", 120, "currency"),
		("当前库存金额", "stock_value", "Currency", 130, "currency"),
		("折旧起算日期", "start_date", "Date", 115, None),
		("本次测算日期", "calculation_date", "Date", 115, None),
		("使用单据类型", "usage_doctype", "Data", 130, None),
		("使用记录来源", "usage_document", "Dynamic Link", 180, "usage_doctype"),
	]
	primary = ["item_code", "period_label", "period_ratio", "basis_rate", "last_usage_time"]
	columns = [dict(label=label, fieldname=name, fieldtype=kind, width=width,
		hidden=int(name not in primary), sticky=name == "item_code",
		**({"options": options} if options else {}))
		for label, name, kind, width, options in definitions]
	return sorted(columns, key=lambda column: primary.index(column["fieldname"])
		if column["fieldname"] in primary else len(primary))


def get_summary(filters=None):
	_check_access()
	filters = _filters(filters)
	assessment_date = getdate(today())
	items, warehouses, companies, rules, bins = _load_candidates(filters)
	rows, issues = _evaluate(rules, items, warehouses, companies, bins, filters, assessment_date)
	usage = get_last_effective_usage([(row.item_code, row.warehouse) for row in rows], now_datetime())
	visible = _visible_sources(usage)
	unknown_count = 0
	for row in rows:
		source = usage.get((row.item_code, row.warehouse))
		row.last_usage_time = source.posting_datetime if source else None
		row.last_activity_date = getdate(source.posting_datetime) if source else None
		row.idle_days = date_diff(assessment_date, row.last_activity_date) if source else None
		row.usage_status = "按本仓有效出库统计" if source else "无有效使用记录，待确认"
		row.usage_doctype = row.usage_document = None
		if source and (source.voucher_type, source.voucher_no) in visible:
			row.usage_doctype, row.usage_document = source.voucher_type, source.voucher_no
		elif source:
			row.usage_status = "有有效使用记录，来源单据无读取权限"
		unknown_count += int(source is None)
	if filters.min_idle_days is not None:
		rows = [row for row in rows if row.idle_days is not None and row.idle_days >= filters.min_idle_days]
	rows.sort(key=lambda row: (row.company, row.item_code, row.warehouse))
	totals = defaultdict(float)
	for row in rows:
		totals[(row.company, row.currency)] += row.impairment_amount
	summary = [
		{"label": "已开始折旧物料数", "value": len({row.item_code for row in rows}), "datatype": "Int"},
		{"label": "仓库记录数", "value": len(rows), "datatype": "Int"},
	]
	for (company, currency), amount in sorted(totals.items()):
		summary.append({"label": f"{company} 建议减值金额", "value": flt(amount, 2), "datatype": "Currency", "currency": currency})
	message = [f"本次测算：{assessment_date}；只读评估，不自动调价或计提。",
		"原始参考单价请按库存单位及公司本位币核对；未使用时间不改变折旧起算日期。",
		f"无有效使用记录：{unknown_count}条；设置未使用天数筛选时，这些记录不计入筛选结果。"]
	if issues:
		message.append(f"本次跳过 {len(issues)} 条规则：")
		message.extend(f"{escape(str(item))}：{escape(reason)}" for item, reason in issues[:30])
		if len(issues) > 30:
			message.append("其余规则请在对应物料中核对。")
	return get_columns(), rows, "<br>".join(message), None, summary, True
