from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today


MODE_DIRECT = "直接确认应收"
MODE_SETTLEMENT = "对账结算后确认应收"
CONFIRM_EXTERNAL = "外部客户确认"
CONFIRM_INTERNAL = "内部复核"
STATUS_DRAFT = "草稿"
STATUS_PENDING_CUSTOMER = "待客户确认"
STATUS_PENDING_INTERNAL = "待内部复核"
STATUS_INVOICED = "已生成应收"
STATUS_CANCELLED = "已取消"

PREPARER_ROLES = ("Sales User", "Accounts User", "Accounts Manager", "China Finance Manager", "System Manager")
MANAGER_ROLES = ("Accounts Manager", "China Finance Manager", "System Manager")


def _has_any_role(roles):
	return bool(set(frappe.get_roles()) & set(roles))


def _require_roles(roles):
	if not _has_any_role(roles):
		frappe.throw(_("无权执行销售结算操作"), frappe.PermissionError)


def _precision(company):
	return frappe.get_precision("Sales Invoice Item", "qty") or 3, frappe.get_precision("Sales Invoice Item", "rate") or 2


def _amount_tolerance(company):
	return flt(frappe.db.get_value("China Finance Settings", company, "reconciliation_tolerance") or 0.01)


def _settings_mode(company, transaction_date):
	settings = frappe.db.get_value(
		"China Finance Settings", company,
		["sales_settlement_mode", "sales_settlement_activation_date"], as_dict=True,
	)
	if not settings:
		return MODE_DIRECT, None, CONFIRM_EXTERNAL
	if not settings.sales_settlement_activation_date or getdate(transaction_date) < getdate(settings.sales_settlement_activation_date):
		return MODE_DIRECT, None, CONFIRM_EXTERNAL
	return settings.sales_settlement_mode or MODE_DIRECT, None, CONFIRM_EXTERNAL


def resolve_sales_settlement_mode(company, customer, transaction_date, override_mode=None):
	"""Resolve only from persisted configuration; callers store the result on the Sales Order."""
	mode, rule, confirmation_method = _settings_mode(company, transaction_date)
	rules = frappe.get_all(
		"China Sales Settlement Rule",
		filters={"company": company, "customer": customer, "enabled": 1, "effective_from": ["<=", transaction_date]},
		fields=["name", "settlement_mode", "confirmation_method", "effective_from", "effective_to"],
		order_by="effective_from desc, modified desc",
	)
	for candidate in rules:
		if not candidate.effective_to or getdate(candidate.effective_to) >= getdate(transaction_date):
			mode, rule, confirmation_method = candidate.settlement_mode, candidate.name, candidate.confirmation_method
			break
	if override_mode:
		mode, rule = override_mode, None
	return {"mode": mode, "rule": rule, "confirmation_method": confirmation_method}


def apply_sales_order_settlement_mode(doc, method=None):
	if doc.doctype != "Sales Order" or not doc.company or not doc.customer:
		return
	if doc.get("custom_china_settlement_mode") and not doc.is_new():
		return
	result = resolve_sales_settlement_mode(doc.company, doc.customer, doc.transaction_date or today())
	doc.custom_china_settlement_mode = result["mode"]
	doc.custom_china_settlement_rule = result["rule"]
	doc.custom_china_settlement_confirmation_method = result["confirmation_method"]


@frappe.whitelist()
def set_sales_order_settlement_override(sales_order, settlement_mode, reason):
	_require_roles(MANAGER_ROLES)
	if settlement_mode not in (MODE_DIRECT, MODE_SETTLEMENT):
		frappe.throw(_("无效的销售结算模式"))
	if not (reason or "").strip():
		frappe.throw(_("修改订单结算模式必须填写原因"))
	doc = frappe.get_doc("Sales Order", sales_order)
	if doc.docstatus != 0:
		frappe.throw(_("仅草稿销售订单可覆盖结算模式"))
	if frappe.db.exists("Delivery Note Item", {"against_sales_order": sales_order, "docstatus": 1}):
		frappe.throw(_("销售订单已有已提交出库，不能修改结算模式"))
	doc.db_set("custom_china_settlement_mode", settlement_mode)
	doc.db_set("custom_china_settlement_rule", None)
	doc.db_set("custom_china_settlement_override", 1)
	doc.db_set("custom_china_settlement_override_reason", reason.strip())
	doc.db_set("custom_china_settlement_override_by", frappe.session.user)
	doc.db_set("custom_china_settlement_override_on", now_datetime())
	return {"name": doc.name, "mode": settlement_mode}


def validate_delivery_note_settlement_mode(doc, method=None):
	if not doc.customer or doc.is_return:
		return
	modes = set()
	confirmation_methods = set()
	for item in doc.items:
		if not item.against_sales_order:
			continue
		values = frappe.db.get_value(
			"Sales Order", item.against_sales_order,
			["custom_china_settlement_mode", "custom_china_settlement_confirmation_method"], as_dict=True,
		)
		if values:
			modes.add(values.custom_china_settlement_mode or MODE_DIRECT)
			confirmation_methods.add(values.custom_china_settlement_confirmation_method or CONFIRM_EXTERNAL)
	if len(modes) > 1:
		frappe.throw(_("一个销售出库单不能混合直接确认应收和对账结算后确认应收的订单"))
	doc.custom_china_settlement_mode = modes.pop() if modes else MODE_DIRECT
	doc.custom_china_settlement_confirmation_method = confirmation_methods.pop() if confirmation_methods else CONFIRM_EXTERNAL


def _active_settled_quantity(delivery_note_item, exclude_settlement=None):
	conditions = "ssi.delivery_note_item=%s AND ss.docstatus=1 AND ss.status=%s"
	values = [delivery_note_item, STATUS_INVOICED]
	if exclude_settlement:
		conditions += " AND ss.name!=%s"
		values.append(exclude_settlement)
	return flt(frappe.db.sql(
		f"""SELECT COALESCE(SUM(ssi.settlement_qty), 0)
		FROM `tabChina Sales Settlement Item` ssi
		INNER JOIN `tabChina Sales Settlement` ss ON ss.name=ssi.parent
		WHERE {conditions}""", values,
	)[0][0])


def _delivery_item_snapshot(delivery_note_item):
	item = frappe.db.get_value(
		"Delivery Note Item", delivery_note_item,
		["name", "parent", "against_sales_order", "item_code", "item_name", "uom", "qty", "rate", "amount", "returned_qty"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("销售出库明细不存在：{0}").format(delivery_note_item))
	delivery = frappe.db.get_value(
		"Delivery Note", item.parent,
		["company", "customer", "currency", "posting_date", "docstatus", "is_return", "taxes_and_charges", "tax_category"], as_dict=True,
	)
	if not delivery or delivery.docstatus != 1 or delivery.is_return:
		frappe.throw(_("仅可结算已提交且非退货的销售出库单"))
	if delivery.company != frappe.db.get_value("Delivery Note", item.parent, "company"):
		frappe.throw(_("销售出库公司不一致"))
	item.update(delivery)
	item.already_settled_qty = _active_settled_quantity(item.name)
	item.remaining_qty = max(0, flt(item.qty) - flt(item.returned_qty) - item.already_settled_qty)
	return item


def _tax_rate_from_delivery(delivery_note, net_amount):
	if not net_amount:
		return 0
	rows = frappe.get_all("Sales Taxes and Charges", filters={"parent": delivery_note, "parenttype": "Delivery Note"}, fields=["rate", "charge_type"])
	return sum(flt(row.rate) for row in rows if row.charge_type == "On Net Total")


def _load_settlement_item(snapshot, settlement_qty=None):
	qty = flt(settlement_qty if settlement_qty is not None else snapshot.remaining_qty)
	tax_rate = _tax_rate_from_delivery(snapshot.parent, flt(snapshot.amount))
	return {
		"delivery_note": snapshot.parent,
		"delivery_note_item": snapshot.name,
		"sales_order": snapshot.against_sales_order,
		"item_code": snapshot.item_code,
		"item_name": snapshot.item_name,
		"uom": snapshot.uom,
		"delivery_date": snapshot.posting_date,
		"delivered_qty": snapshot.qty,
		"already_settled_qty": snapshot.already_settled_qty,
		"remaining_qty": snapshot.remaining_qty,
		"settlement_qty": qty,
		"original_rate": snapshot.rate,
		"settlement_rate": snapshot.rate,
		"discount_amount": 0,
		"tax_rate": tax_rate,
	}


@frappe.whitelist()
def get_settleable_delivery_items(delivery_notes):
	_require_roles(PREPARER_ROLES)
	names = frappe.parse_json(delivery_notes) if isinstance(delivery_notes, str) else delivery_notes
	result = []
	for name in names or []:
		for item in frappe.get_all("Delivery Note Item", {"parent": name}, pluck="name"):
			snapshot = _delivery_item_snapshot(item)
			mode = frappe.db.get_value("Delivery Note", name, "custom_china_settlement_mode")
			if mode == MODE_SETTLEMENT and snapshot.remaining_qty > 0:
				result.append(_load_settlement_item(snapshot))
	return result


def _validate_header(doc):
	if not doc.company or not doc.customer or not doc.currency:
		frappe.throw(_("销售结算单必须填写公司、客户和币种"))
	if not doc.items:
		frappe.throw(_("销售结算单至少需要一条结算明细"))
	if doc.status in (STATUS_INVOICED, STATUS_CANCELLED) and not doc.flags.ignore_settlement_state:
		frappe.throw(_("已完成或已取消的销售结算单不可修改"))


def validate_sales_settlement(doc):
	_validate_header(doc)
	# Derive the display status from the confirmation method while the document is a draft.
	if doc.docstatus == 0:
		doc.status = STATUS_PENDING_CUSTOMER if doc.confirmation_method == CONFIRM_EXTERNAL else STATUS_PENDING_INTERNAL
	qty_precision, rate_precision = _precision(doc.company)
	dates = []
	adjustment_count = 0
	for row in doc.items:
		settlement_rate = row.settlement_rate
		discount_amount = row.discount_amount
		adjustment_reason = row.adjustment_reason
		snapshot = _delivery_item_snapshot(row.delivery_note_item)
		if snapshot.company != doc.company or snapshot.customer != doc.customer or snapshot.currency != doc.currency:
			frappe.throw(_("结算明细必须来自同一公司、客户和币种的销售出库单"))
		if frappe.db.get_value("Delivery Note", snapshot.parent, "custom_china_settlement_mode") != MODE_SETTLEMENT:
			frappe.throw(_("销售出库单 {0} 未启用对账结算模式").format(snapshot.parent))
		if flt(row.settlement_qty, qty_precision) <= 0 or flt(row.settlement_qty, qty_precision) > flt(snapshot.remaining_qty, qty_precision):
			frappe.throw(_("物料 {0} 的结算数量超过剩余可结算数量").format(row.item_code))
		row.update(_load_settlement_item(snapshot, row.settlement_qty))
		row.settlement_rate = flt(settlement_rate if settlement_rate is not None else snapshot.rate, rate_precision)
		row.discount_amount = flt(discount_amount, rate_precision)
		row.adjustment_reason = adjustment_reason
		row.net_amount = flt(row.settlement_qty * row.settlement_rate - row.discount_amount, rate_precision)
		if row.net_amount < 0:
			frappe.throw(_("物料 {0} 的折扣/扣款不能超过结算金额").format(row.item_code))
		row.tax_amount = flt(row.net_amount * flt(row.tax_rate) / 100, rate_precision)
		row.settlement_amount = flt(row.net_amount + row.tax_amount, rate_precision)
		if any((flt(row.settlement_qty) != flt(snapshot.remaining_qty), flt(row.settlement_rate) != flt(snapshot.rate), flt(row.discount_amount))):
			adjustment_count += 1
			if not (row.adjustment_reason or "").strip():
				frappe.throw(_("物料 {0} 的数量、单价或扣款调整必须填写原因").format(row.item_code))
		dates.append(getdate(snapshot.posting_date))
	doc.adjustment_count = adjustment_count
	doc.from_date = min(dates) if dates else None
	doc.to_date = max(dates) if dates else None


def _validate_combination_compatibility(doc):
	values = set()
	for delivery_note in {row.delivery_note for row in doc.items}:
		delivery = frappe.db.get_value("Delivery Note", delivery_note, ["taxes_and_charges", "tax_category", "selling_price_list"], as_dict=True)
		values.add((delivery.taxes_and_charges or "", delivery.tax_category or "", delivery.selling_price_list or ""))
	if len(values) > 1:
		frappe.throw(_("合并结算的销售出库单必须使用相同的税费模板、税务类别和价目表"))


@frappe.whitelist()
def create_settlement_from_delivery_notes(delivery_notes, posting_date=None):
	_require_roles(PREPARER_ROLES)
	items = get_settleable_delivery_items(delivery_notes)
	if not items:
		frappe.throw(_("没有可结算的销售出库明细"))
	first = frappe.db.get_value("Delivery Note", items[0]["delivery_note"], ["company", "customer", "currency", "custom_china_settlement_confirmation_method"], as_dict=True)
	doc = frappe.get_doc({
		"doctype": "China Sales Settlement", "company": first.company, "customer": first.customer,
		"customer_name": frappe.db.get_value("Customer", first.customer, "customer_name"), "currency": first.currency,
		"posting_date": posting_date or today(), "status": STATUS_DRAFT,
		"confirmation_method": first.custom_china_settlement_confirmation_method or CONFIRM_EXTERNAL,
		"items": items,
	})
	doc.insert()
	return {"name": doc.name}


def validate_settlement_confirmation(doc):
	if doc.confirmation_method == CONFIRM_EXTERNAL and not doc.confirmation_file:
		frappe.throw(_("外部客户确认必须上传回函、邮件或平台文件后才能提交"))
	if doc.confirmation_method == CONFIRM_INTERNAL and not (doc.internal_confirmation_reason or "").strip():
		frappe.throw(_("内部复核必须填写原因后才能提交"))


def _lock_and_validate_balance(doc):
	qty_precision, _ = _precision(doc.company)
	for row in doc.items:
		frappe.db.sql("SELECT name FROM `tabDelivery Note Item` WHERE name=%s FOR UPDATE", row.delivery_note_item)
		snapshot = _delivery_item_snapshot(row.delivery_note_item)
		if flt(row.settlement_qty, qty_precision) > flt(snapshot.remaining_qty, qty_precision):
			frappe.throw(_("销售出库明细 {0} 已被其他结算单占用，剩余数量不足").format(row.delivery_note_item))


def _make_sales_invoice(doc):
	from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

	_validate_combination_compatibility(doc)
	invoice = None
	grouped_rows = defaultdict(list)
	for row in doc.items:
		grouped_rows[row.delivery_note].append(row)
	for delivery_note, rows in grouped_rows.items():
		mapped = make_sales_invoice(delivery_note, args={"filtered_children": [row.delivery_note_item for row in rows]})
		if invoice is None:
			invoice = mapped
		else:
			for item in mapped.items:
				invoice.append("items", item.as_dict())
	if not invoice:
		frappe.throw(_("无法由销售出库单生成正式销售发票"))
	invoice.posting_date = doc.posting_date
	invoice.set_posting_time = 0
	invoice.custom_china_sales_settlement = doc.name
	by_delivery_item = {row.delivery_note_item: row for row in doc.items}
	for item in invoice.items:
		row = by_delivery_item.get(item.dn_detail)
		if not row:
			continue
		item.qty = row.settlement_qty
		item.rate = row.settlement_rate
		item.discount_amount = row.discount_amount
		item.discount_percentage = 0
		item.amount = flt(item.qty * item.rate - item.discount_amount)
		item.base_amount = flt(item.amount * flt(invoice.conversion_rate or 1))
	invoice.run_method("set_missing_values")
	invoice.calculate_taxes_and_totals()
	return invoice


def create_receivable_for_settlement(doc):
	"""Create and submit the Sales Invoice; called from the settlement's before_submit hook."""
	if not frappe.has_permission("Sales Invoice", "create") or not frappe.has_permission("Sales Invoice", "submit"):
		frappe.throw(_("当前用户没有创建和提交 ERPNext 销售发票的权限"), frappe.PermissionError)
	_lock_and_validate_balance(doc)
	invoice = _make_sales_invoice(doc)
	invoice.insert()
	try:
		frappe.flags.china_sales_settlement_approval = doc.name
		invoice.submit()
	finally:
		frappe.flags.china_sales_settlement_approval = None
	doc.sales_invoice = invoice.name
	doc.status = STATUS_INVOICED
	doc.customer_confirmed_by = frappe.session.user
	doc.customer_confirmed_on = now_datetime()
	doc.finance_approved_by = frappe.session.user
	doc.finance_approved_on = now_datetime()
	for row in doc.items:
		for invoice_item in invoice.items:
			if invoice_item.dn_detail == row.delivery_note_item:
				row.sales_invoice_item = invoice_item.name
				break
	refresh_settlement_summaries(doc)


def validate_sales_invoice_settlement(doc, method=None):
	if doc.is_return:
		return
	settlement_mode_deliveries = {
		item.delivery_note for item in doc.items
		if item.delivery_note and frappe.db.get_value("Delivery Note", item.delivery_note, "custom_china_settlement_mode") == MODE_SETTLEMENT
	}
	if not settlement_mode_deliveries:
		return
	settlement_name = doc.get("custom_china_sales_settlement")
	if not settlement_name or frappe.flags.get("china_sales_settlement_approval") != settlement_name:
		frappe.throw(_("对账结算模式的销售出库必须通过已审批的销售结算单生成正式销售发票"))
	settlement = frappe.get_doc("China Sales Settlement", settlement_name)
	if settlement.docstatus == 2 or settlement.status == STATUS_CANCELLED:
		frappe.throw(_("销售结算单已取消，不能生成正式销售发票"))


def handle_sales_invoice_cancellation(doc, method=None):
	settlement_name = doc.get("custom_china_sales_settlement")
	if not settlement_name or not frappe.db.exists("China Sales Settlement", settlement_name):
		return
	settlement = frappe.get_doc("China Sales Settlement", settlement_name)
	if settlement.docstatus == 1 and settlement.status == STATUS_INVOICED:
		settlement.db_set("status", STATUS_CANCELLED, update_modified=False)
		settlement.db_set("cancellation_reason", _("正式销售发票 {0} 已取消，结算结果失效").format(doc.name), update_modified=False)
		refresh_settlement_summaries(settlement)


def refresh_settlement_summaries(settlement):
	for delivery_note in {row.delivery_note for row in settlement.items}:
		rows = frappe.db.sql(
			"""SELECT ssi.settlement_amount, ssi.settlement_qty
			FROM `tabChina Sales Settlement Item` ssi
			INNER JOIN `tabChina Sales Settlement` ss ON ss.name=ssi.parent
			WHERE ssi.delivery_note=%s AND ss.docstatus=1 AND ss.status=%s""",
			(delivery_note, STATUS_INVOICED), as_dict=True,
		)
		settled_amount = sum(flt(row.settlement_amount) for row in rows)
		delivery = frappe.get_doc("Delivery Note", delivery_note)
		delivery.db_set("custom_china_settled_amount", settled_amount, update_modified=False)
		delivery.db_set("custom_china_pending_settlement_amount", max(0, flt(delivery.grand_total) - settled_amount), update_modified=False)
		for order in {row.sales_order for row in settlement.items if row.sales_order}:
			order_rows = frappe.db.sql(
				"""SELECT ssi.settlement_amount FROM `tabChina Sales Settlement Item` ssi
				INNER JOIN `tabChina Sales Settlement` ss ON ss.name=ssi.parent
				WHERE ssi.sales_order=%s AND ss.docstatus=1 AND ss.status=%s""",
				(order, STATUS_INVOICED), as_dict=True,
			)
			frappe.db.set_value("Sales Order", order, "custom_china_settled_amount", sum(flt(row.settlement_amount) for row in order_rows), update_modified=False)


def get_sales_settlement_closing_check(company, from_date, to_date):
	rows = frappe.db.sql(
		"""
		SELECT dni.parent AS delivery_note, dni.name AS delivery_note_item, dni.item_code,
			GREATEST(0, dni.qty - COALESCE(dni.returned_qty, 0) - COALESCE(SUM(CASE WHEN ss.docstatus=1 AND ss.status=%s THEN ssi.settlement_qty ELSE 0 END), 0)) AS pending_qty,
			GREATEST(0, dni.amount - COALESCE(SUM(CASE WHEN ss.docstatus=1 AND ss.status=%s THEN ssi.net_amount ELSE 0 END), 0)) AS pending_amount
		FROM `tabDelivery Note Item` dni
		INNER JOIN `tabDelivery Note` dn ON dn.name=dni.parent
		LEFT JOIN `tabChina Sales Settlement Item` ssi ON ssi.delivery_note_item=dni.name
		LEFT JOIN `tabChina Sales Settlement` ss ON ss.name=ssi.parent
		WHERE dn.company=%s AND dn.posting_date BETWEEN %s AND %s AND dn.docstatus=1 AND dn.is_return=0
			AND dn.custom_china_settlement_mode=%s
		GROUP BY dni.name HAVING pending_qty>0.0001 OR pending_amount>0.01
		""", (STATUS_INVOICED, STATUS_INVOICED, company, from_date, to_date, MODE_SETTLEMENT), as_dict=True,
	)
	return {
		"passed": not rows,
		"count": len(rows),
		"amount": sum(flt(row.pending_amount) for row in rows),
		"details": _("已出库但未完成正式结算 {0} 条，金额 {1}").format(len(rows), sum(flt(row.pending_amount) for row in rows)),
		"rows": rows,
	}


def get_sales_settlement_dashboard(company, from_date, to_date):
	draft = frappe.db.count("China Sales Settlement", {"company": company, "docstatus": 0})
	coverage = get_sales_settlement_closing_check(company, from_date, to_date)
	return {"draft": draft, "coverage": coverage}
