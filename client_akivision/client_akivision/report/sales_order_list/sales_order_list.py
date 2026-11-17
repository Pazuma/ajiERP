import frappe
from frappe import _
from frappe.utils import flt, getdate

from client_akivision.utils.sales_order_completion import get_sales_order_invoice_payment_details


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data), 1


def get_report_summary(data):
	order_rows = [row for row in data if row.get("indent") == 0]
	item_rows = [row for row in data if row.get("indent") == 1]
	delivered = sum(1 for row in item_rows if row.get("completion_status") == _("已交货"))
	final_completed = sum(1 for row in order_rows if row.get("final_status") == _("已完成"))
	high_tech_total = sum(
		flt(row.get("amount")) for row in order_rows if row.get("is_high_tech") == _("是")
	)
	return [
		{"value": len(order_rows), "label": _("销售订单数"), "datatype": "Int", "indicator": "Blue"},
		{"value": len(item_rows), "label": _("订单明细行"), "datatype": "Int", "indicator": "Blue"},
		{"value": sum(flt(row.get("amount")) for row in order_rows), "label": _("订单金额"), "datatype": "Currency", "indicator": "Green"},
		{"value": high_tech_total, "label": _("High-tech Revenue Amount"), "datatype": "Currency", "indicator": "Orange"},
		{"value": delivered, "label": _("已交货明细行"), "datatype": "Int", "indicator": "Green"},
		{"value": final_completed, "label": _("已收款完成订单"), "datatype": "Int", "indicator": "Green"},
	]


def get_columns():
	return [
		{"label": _("Sales Order / Item"), "fieldname": "name", "fieldtype": "Data", "width": 180},
		{"label": _("Year"), "fieldname": "year", "fieldtype": "Int", "width": 70},
		{"label": _("Month"), "fieldname": "month", "fieldtype": "Int", "width": 60},
		{"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{
			"label": _("Customer Code"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 110,
		},
		{"label": _("Customer PO No"), "fieldname": "po_no", "fieldtype": "Data", "width": 140},
		{
			"label": _("Product Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": _("Model"), "fieldname": "external_model", "fieldtype": "Data", "width": 140},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Tax Inclusive Price"), "fieldname": "rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Order Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Delivery Status"), "fieldname": "completion_status", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Status"), "fieldname": "invoice_status", "fieldtype": "Data", "width": 120},
		{"label": _("Collection Status"), "fieldname": "collection_status", "fieldtype": "Data", "width": 120},
		{"label": _("Final Order Status"), "fieldname": "final_status", "fieldtype": "Data", "width": 130},
		{"label": _("Completion Flag"), "fieldname": "completion_flag", "fieldtype": "Data", "width": 100},
		{"label": _("High-tech Revenue"), "fieldname": "is_high_tech", "fieldtype": "Data", "width": 110},
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Data", "width": 100},
		{"label": _("Payment Terms"), "fieldname": "payment_terms_template", "fieldtype": "Data", "width": 140},
		{"label": _("Credit Days"), "fieldname": "credit_days", "fieldtype": "Int", "width": 80},
		{"label": _("Invoice No"), "fieldname": "invoice_no", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Date"), "fieldname": "invoice_date", "fieldtype": "Date", "width": 100},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 180},
		{"label": _("Received Amount"), "fieldname": "received_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Reconciliation Period"), "fieldname": "reconciliation_period", "fieldtype": "Data", "width": 120},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 160},
		{"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
		{"label": _("Cumulative Delivered Qty"), "fieldname": "delivered_qty", "fieldtype": "Float", "width": 140},
		{"label": _("Item Completed"), "fieldname": "item_completed", "fieldtype": "Data", "width": 100},
		{"label": _("Order Fully Completed"), "fieldname": "order_fully_completed", "fieldtype": "Data", "width": 120},
		{"label": _("Undelivered Qty"), "fieldname": "undelivered_qty", "fieldtype": "Float", "width": 120},
	]


def get_data(filters):
	conditions = get_conditions(filters)
	rows = frappe.db.sql(
		f"""
		SELECT
			so.name AS sales_order,
			so.transaction_date,
			so.customer,
			so.customer_name,
			so.po_no,
			so.payment_terms_template,
			so.delivery_date,
			so.grand_total,
			so.per_billed,
			so.custom_is_high_tech_revenue,
			so.custom_remarks,
			soi.item_code,
			soi.item_name,
			soi.name AS so_item_name,
			soi.qty,
			soi.uom,
			soi.rate,
			soi.amount,
			soi.delivered_qty,
			soi.idx AS item_idx,
			(SELECT GROUP_CONCAT(st.sales_person SEPARATOR ', ')
			 FROM `tabSales Team` st WHERE st.parent = so.name) AS sales_person
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		WHERE so.docstatus = 1 {conditions}
		ORDER BY so.transaction_date DESC, so.name DESC, soi.idx
		""",
		filters,
		as_dict=True,
	)

	if not rows:
		return []

	sales_order_names = list({row.sales_order for row in rows})
	item_codes = list({row.item_code for row in rows if row.item_code})

	# Item details
	item_fields = ["name", "item_group", "custom_internal_model", "custom_external_model"]
	item_details = {
		row.name: row
		for row in frappe.get_all("Item", filters={"name": ["in", item_codes]}, fields=item_fields)
	}

	# Delivery Note quantities per Sales Order Item
	delivery_qty = get_delivered_qty_map(sales_order_names)

	# Invoice and allocated payment details per Sales Order
	invoice_payment_details = get_sales_order_invoice_payment_details(sales_order_names)

	# SO-level totals for full completion flag
	so_totals = get_so_totals(sales_order_names)

	item_data = []
	for row in rows:
		item = item_details.get(row.item_code, {})
		delivered = flt(delivery_qty.get((row.sales_order, row.item_code, row.so_item_name)))
		undelivered = flt(row.qty) - delivered
		item_completed = 1 if delivered >= flt(row.qty) else 0
		so_total = so_totals.get(row.sales_order, {})
		order_fully_completed = 1 if so_total.get("total") == so_total.get("completed", 0) and so_total.get("total") else 0

		completion_status = get_completion_status(delivered, row.qty)

		invoice_payment = invoice_payment_details.get(row.sales_order, {})
		invoice_status = get_invoice_status(row.per_billed, invoice_payment.get("has_invoice"))
		collection_status = invoice_payment.get("collection_status", "未收款")
		final_status = get_final_status(
			completion_status,
			bool(order_fully_completed),
			invoice_status,
			invoice_payment.get("all_paid", False),
			collection_status,
		)

		item_data.append(
			frappe._dict(
				{
				"sales_order": row.sales_order,
				"grand_total": flt(row.grand_total),
				"year": getdate(row.transaction_date).year,
				"month": getdate(row.transaction_date).month,
				"transaction_date": row.transaction_date,
				"customer_name": row.customer_name,
				"customer": row.customer,
				"po_no": row.po_no,
				"item_code": row.item_code,
				"external_model": item.get("custom_external_model") or "",
				"uom": row.uom,
				"qty": flt(row.qty),
				"rate": flt(row.rate),
				"amount": flt(row.amount),
				"completion_status": completion_status,
				"invoice_status": invoice_status,
				"collection_status": collection_status,
				"final_status": final_status,
				"completion_flag": "已完成" if item_completed else "未完成",
				"is_high_tech": "是" if row.custom_is_high_tech_revenue else "否",
				"sales_person": row.sales_person or "",
				"payment_terms_template": row.payment_terms_template or "",
				"credit_days": get_credit_days(row.payment_terms_template),
				"invoice_no": invoice_payment.get("invoice_no") or "",
				"invoice_date": invoice_payment.get("invoice_date"),
				"remarks": row.custom_remarks or "",
				"received_amount": flt(invoice_payment.get("received_amount", 0)),
				"outstanding_amount": flt(invoice_payment.get("outstanding_amount", flt(row.amount))),
				"reconciliation_period": "",
				"due_date": row.delivery_date,
				"item_name": row.item_name,
				"delivery_date": row.delivery_date,
				"delivered_qty": delivered,
				"item_completed": "是" if item_completed else "否",
				"order_fully_completed": "是" if order_fully_completed else "否",
				"undelivered_qty": undelivered,
				}
			)
		)

	if filters.get("status") or filters.get("is_high_tech"):
		data = make_tree_data(item_data)
		matching_orders = {
			row.name
			for row in data
			if row.indent == 0
			and (not filters.status or filters.status in {
				row.completion_status,
				row.invoice_status,
				row.collection_status,
				row.final_status,
			})
			and (not filters.is_high_tech or row.is_high_tech == filters.is_high_tech)
		}
		return [row for row in data if row.get("sales_order") in matching_orders]

	return make_tree_data(item_data)


def make_tree_data(item_data):
	"""Return order-level parent rows followed by their item-level children."""
	data = []
	orders = {}
	for item_row in item_data:
		sales_order = item_row.sales_order
		if sales_order not in orders:
			order_status = get_order_status(item_row)
			orders[sales_order] = frappe._dict({
				"name": sales_order,
				"name_display": sales_order,
				"sales_order": sales_order,
				"parent": None,
				"indent": 0,
				"is_group": 1,
				"year": item_row.year,
				"month": item_row.month,
				"transaction_date": item_row.transaction_date,
				"customer_name": item_row.customer_name,
				"customer": item_row.customer,
				"po_no": item_row.po_no,
				"amount": flt(item_row.grand_total),
				"completion_status": order_status,
				"invoice_status": item_row.invoice_status,
				"collection_status": item_row.collection_status,
				"final_status": item_row.final_status,
				"completion_flag": "已完成" if item_row.final_status == _("已完成") else "未完成",
				"is_high_tech": item_row.is_high_tech,
				"sales_person": item_row.sales_person,
				"payment_terms_template": item_row.payment_terms_template,
				"credit_days": item_row.credit_days,
				"invoice_no": item_row.invoice_no,
				"invoice_date": item_row.invoice_date,
				"remarks": item_row.remarks,
				"received_amount": item_row.received_amount,
				"outstanding_amount": item_row.outstanding_amount,
				"due_date": item_row.due_date,
				"delivery_date": item_row.delivery_date,
				"order_fully_completed": item_row.order_fully_completed,
			})
			data.append(orders[sales_order])
		elif (
			orders[sales_order]["completion_status"] == _("未交货")
			and flt(item_row.delivered_qty) > 0
		):
			orders[sales_order]["completion_status"] = _("交货中")

		item_row.name = f"{sales_order}-{item_row.item_idx}"
		item_row.name_display = item_row.item_name or item_row.item_code
		item_row.parent = sales_order
		item_row.indent = 1
		item_row.is_group = 0
		item_row.year = None
		item_row.month = None
		item_row.transaction_date = None
		item_row.customer_name = None
		item_row.customer = None
		item_row.po_no = None
		item_row.is_high_tech = None
		item_row.sales_person = None
		item_row.payment_terms_template = None
		item_row.credit_days = None
		item_row.invoice_no = None
		item_row.invoice_date = None
		item_row.remarks = None
		item_row.received_amount = None
		item_row.outstanding_amount = None
		item_row.reconciliation_period = None
		item_row.due_date = None
		item_row.order_fully_completed = None
		item_row.invoice_status = None
		item_row.collection_status = None
		item_row.final_status = None
		data.append(item_row)

	return data


def get_order_status(item_row):
	if item_row.order_fully_completed == "是":
		return _("已交货")
	if flt(item_row.delivered_qty) > 0:
		return _("交货中")
	return _("未交货")


def get_delivered_qty_map(sales_order_names):
	if not sales_order_names:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			dni.against_sales_order AS sales_order,
			dni.so_detail,
			dni.item_code,
			SUM(dni.qty) AS qty
		FROM `tabDelivery Note Item` dni
		INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
		WHERE dn.docstatus = 1
		  AND dni.against_sales_order IN %s
		GROUP BY dni.against_sales_order, dni.so_detail, dni.item_code
		""",
		(tuple(sales_order_names),),
		as_dict=True,
	)

	return {
		(row.sales_order, row.item_code, row.so_detail): flt(row.qty)
		for row in rows
	}


def get_so_totals(sales_order_names):
	if not sales_order_names:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			so.name,
			COUNT(soi.name) AS total_items,
			SUM(CASE WHEN soi.delivered_qty >= soi.qty THEN 1 ELSE 0 END) AS completed_items
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		WHERE so.name IN %s
		GROUP BY so.name
		""",
		(tuple(sales_order_names),),
		as_dict=True,
	)

	return {
		row.name: {"total": row.total_items, "completed": row.completed_items}
		for row in rows
	}


def get_completion_status(delivered_qty, order_qty):
	if delivered_qty >= flt(order_qty):
		return _("已交货")
	elif delivered_qty > 0:
		return _("交货中")
	return _("未交货")


def get_invoice_status(per_billed, has_invoice):
	if not has_invoice:
		return _("未开票")
	return _("已开票") if flt(per_billed) >= 100 else _("部分开票")


def get_final_status(delivery_status, all_delivered, invoice_status, all_paid, collection_status):
	if not all_delivered:
		return delivery_status
	if invoice_status != _("已开票"):
		return _("待开票")
	if all_paid:
		return _("已完成")
	if collection_status == _("部分收款"):
		return _("部分收款")
	return _("待收款")


def get_credit_days(payment_terms_template):
	if not payment_terms_template:
		return 0
	if not frappe.get_meta("Payment Terms Template").has_field("custom_credit_days"):
		return 0
	return flt(frappe.db.get_value("Payment Terms Template", payment_terms_template, "custom_credit_days")) or 0


def get_conditions(filters):
	conditions = []
	from client_akivision.utils.order_record_permissions import get_order_scope_condition, is_scoped_user

	if is_scoped_user("Sales Order"):
		conditions.append(f"AND ({get_order_scope_condition('Sales Order', alias='so')})")
	if filters.get("company"):
		conditions.append("AND so.company = %(company)s")
	if filters.get("customer"):
		conditions.append("AND so.customer = %(customer)s")
	if filters.get("from_date"):
		conditions.append("AND so.transaction_date >= %(from_date)s")
	if filters.get("to_date"):
		conditions.append("AND so.transaction_date <= %(to_date)s")
	if filters.get("sales_person"):
		conditions.append(
			"AND EXISTS (SELECT 1 FROM `tabSales Team` st WHERE st.parent = so.name AND st.sales_person = %(sales_person)s)"
		)
	return " ".join(conditions)
