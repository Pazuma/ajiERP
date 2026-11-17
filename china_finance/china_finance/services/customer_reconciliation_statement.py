"""Read-only customer reconciliation data loading for China Reconciliation Statement."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt, getdate


RECONCILIATION_USERS = ("System Manager", "Accounts Manager", "Accounts User", "China Finance Manager")


def _validate_filters(company, customer, from_date, to_date):
	if not company or not customer or not from_date or not to_date:
		frappe.throw(_("公司、客户、起始日期和截止日期均为必填项"))
	if getdate(from_date) > getdate(to_date):
		frappe.throw(_("起始日期不能晚于截止日期"))
	if not frappe.has_permission("Customer", ptype="read", doc=customer):
		frappe.throw(_("没有读取该客户的权限"))
	if not frappe.db.exists("Company", company):
		frappe.throw(_("公司不存在"))


def _transaction_category(voucher_type, debit, credit):
	if voucher_type == "Sales Invoice":
		return _("销售发票/贷项")
	if voucher_type == "Payment Entry":
		return _("收款/退款")
	if voucher_type == "Journal Entry":
		return _("调整凭证")
	return _("其他账款变动")


def _snapshot_key(company, customer, from_date, to_date, rows):
	payload = {
		"company": company,
		"customer": customer,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"entries": [
			[row.name, str(row.modified), flt(row.debit), flt(row.credit)] for row in rows
		],
	}
	return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _names(values):
	return ", ".join(sorted({str(value) for value in values if value}))


def _invoice_links(invoice_names):
	"""Return multi-valued order/delivery links for submitted sales invoices."""
	if not invoice_names:
		return {}
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", list(invoice_names)], "docstatus": 1},
		fields=["parent", "sales_order", "delivery_note", "so_detail"],
	)
	links = {name: {"sales_orders": set(), "delivery_notes": set(), "customer_po_no": ""} for name in invoice_names}
	for item in items:
		bucket = links.setdefault(item.parent, {"sales_orders": set(), "delivery_notes": set(), "customer_po_no": ""})
		if item.sales_order:
			bucket["sales_orders"].add(item.sales_order)
		if item.delivery_note:
			bucket["delivery_notes"].add(item.delivery_note)
	order_names = {order for value in links.values() for order in value["sales_orders"]}
	if order_names:
		po_numbers = {row.name: row.po_no or "" for row in frappe.get_all(
			"Sales Order", filters={"name": ["in", list(order_names)]}, fields=["name", "po_no"]
		)}
		for bucket in links.values():
			bucket["customer_po_no"] = _names(po_numbers.get(order) for order in bucket["sales_orders"])
	return links


def get_opening_customer_documents(company, customer, from_date):
	"""Return submitted invoices and historical payment allocation before from_date."""
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": company, "customer": customer, "posting_date": ["<", from_date],
			"docstatus": 1,
		},
		fields=["name", "posting_date", "grand_total", "currency", "is_return"],
		order_by="posting_date asc, name asc",
	)
	if not invoices:
		return {"documents": [], "adjustment": 0}
	names = [row.name for row in invoices]
	links = _invoice_links(names)
	paid = {name: 0 for name in names}
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"reference_doctype": "Sales Invoice", "reference_name": ["in", names]},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	pe_names = {row.parent for row in refs}
	pe_dates = {
		row.name: row.posting_date
		for row in frappe.get_all("Payment Entry", filters={"name": ["in", list(pe_names)], "docstatus": 1}, fields=["name", "posting_date"])
	}
	for ref in refs:
		if ref.parent in pe_dates and getdate(pe_dates[ref.parent]) < getdate(from_date):
			paid[ref.reference_name] = flt(paid.get(ref.reference_name)) + flt(ref.allocated_amount)
	documents = []
	for invoice in invoices:
		bucket = links.get(invoice.name, {})
		original = flt(invoice.grand_total)
		settled = flt(paid.get(invoice.name))
		outstanding = original - settled
		if abs(outstanding) <= 0.000001:
			continue
		documents.append({
			"posting_date": invoice.posting_date,
			"sales_invoice": invoice.name,
			"customer_po_no": bucket.get("customer_po_no", ""),
			"related_sales_orders": _names(bucket.get("sales_orders", set())),
			"related_delivery_notes": _names(bucket.get("delivery_notes", set())),
			"original_amount": original,
			"settled_amount": settled,
			"outstanding_amount": outstanding,
			"currency": invoice.currency,
			"snapshot_reference": f"Sales Invoice:{invoice.name}",
		})
	return {"documents": documents, "adjustment": 0}


def get_customer_order_billing_details(company, customer, from_date, to_date):
	"""Build order/item billing snapshots without changing source documents."""
	orders = frappe.get_all(
		"Sales Order",
		filters={"company": company, "customer": customer, "transaction_date": ["between", [from_date, to_date]], "docstatus": 1},
		fields=["name", "transaction_date", "po_no", "currency"],
		order_by="transaction_date asc, name asc",
	)
	if not orders:
		return []
	order_names = [row.name for row in orders]
	order_map = {row.name: row for row in orders}
	items = frappe.get_all(
		"Sales Order Item",
		filters={"parent": ["in", order_names], "docstatus": 1},
		fields=["name", "parent", "item_code", "item_name", "uom", "qty", "amount", "rate"],
		order_by="parent asc, idx asc",
	)
	result = []
	for item in items:
		order = order_map[item.parent]
		deliveries = frappe.get_all(
			"Delivery Note Item",
			filters={"against_sales_order": item.parent, "so_detail": item.name, "docstatus": 1},
			fields=["parent", "qty"],
		)
		invoices = frappe.get_all(
			"Sales Invoice Item",
			filters={"sales_order": item.parent, "so_detail": item.name, "docstatus": 1},
			fields=["parent", "qty", "amount"],
		)
		invoice_names = {row.parent for row in invoices}
		paid = 0
		if invoice_names:
			payment_refs = frappe.get_all(
				"Payment Entry Reference",
				filters={"reference_doctype": "Sales Invoice", "reference_name": ["in", list(invoice_names)]},
				fields=["parent", "allocated_amount"],
			)
			payment_dates = {
				row.name: row.posting_date
				for row in frappe.get_all(
					"Payment Entry",
					filters={"name": ["in", [ref.parent for ref in payment_refs]], "docstatus": 1},
					fields=["name", "posting_date"],
				)
			}
			paid = sum(
				flt(ref.allocated_amount)
				for ref in payment_refs
				if ref.parent in payment_dates and getdate(payment_dates[ref.parent]) <= getdate(to_date)
			)
		billed_amount = sum(flt(row.amount) for row in invoices)
		billed_qty = sum(flt(row.qty) for row in invoices)
		if not invoices:
			billing_status = "未开票"
		elif billed_qty + 0.000001 < flt(item.qty):
			billing_status = "部分开票"
		else:
			billing_status = "已开票"
		result.append({
			"order_date": order.transaction_date, "sales_order": order.name, "customer_po_no": order.po_no or "",
			"item_code": item.item_code, "item_name": item.item_name, "uom": item.uom,
			"ordered_qty": flt(item.qty), "delivered_qty": sum(flt(row.qty) for row in deliveries),
			"billed_qty": billed_qty, "order_amount": flt(item.amount),
			"billed_amount": billed_amount, "paid_amount": paid,
			"outstanding_amount": billed_amount - paid,
			"delivery_notes": _names(row.parent for row in deliveries),
			"sales_invoices": _names(invoice_names), "billing_status": billing_status,
			"payment_status": "已结清" if billed_amount and abs(billed_amount - paid) <= 0.000001 else ("部分收款" if paid else "未收款"),
			"included_reason": "期间订单", "currency": order.currency,
		})
	return result


def enrich_customer_ledger_rows(rows, to_date=None):
	invoice_names = {row.get("voucher_no") for row in rows if row.get("voucher_type") == "Sales Invoice"}
	payment_references = {}
	for row in rows:
		if row.get("voucher_type") != "Payment Entry":
			continue
		references = frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": row.get("voucher_no"), "reference_doctype": "Sales Invoice"},
			fields=["reference_name"],
		)
		payment_references[row.get("voucher_no")] = references
		invoice_names.update(reference.reference_name for reference in references)
	links = _invoice_links(invoice_names)
	invoice_amounts = {}
	settled_amounts = {name: 0 for name in invoice_names}
	if invoice_names:
		invoice_amounts = {row.name: flt(row.grand_total) for row in frappe.get_all(
			"Sales Invoice", filters={"name": ["in", list(invoice_names)], "docstatus": 1}, fields=["name", "grand_total"]
		)}
		refs = frappe.get_all("Payment Entry Reference", filters={"reference_doctype": "Sales Invoice", "reference_name": ["in", list(invoice_names)]}, fields=["parent", "reference_name", "allocated_amount"])
		pe_names = {ref.parent for ref in refs}
		payment_filters = {"name": ["in", list(pe_names)], "docstatus": 1}
		if to_date:
			payment_filters["posting_date"] = ["<=", to_date]
		valid_pe = {row.name for row in frappe.get_all("Payment Entry", filters=payment_filters, fields=["name"])}
		for ref in refs:
			if ref.parent in valid_pe:
				settled_amounts[ref.reference_name] = flt(settled_amounts.get(ref.reference_name)) + flt(ref.allocated_amount)
	for row in rows:
		if row.get("voucher_type") == "Sales Invoice":
			bucket = links.get(row.get("voucher_no"), {})
			row["sales_invoice"] = row.get("voucher_no")
			row["related_sales_orders"] = _names(bucket.get("sales_orders", set()))
			row["related_delivery_notes"] = _names(bucket.get("delivery_notes", set()))
			row["customer_po_no"] = bucket.get("customer_po_no", "")
			original = flt(invoice_amounts.get(row.get("voucher_no")))
			settled = flt(settled_amounts.get(row.get("voucher_no")))
			row.update({"original_amount": original, "settled_amount": settled, "outstanding_amount": original - settled,
				"billing_status": "已开票", "payment_status": "已收款" if original and settled >= original - 0.000001 else ("部分收款" if settled else "未收款")})
		elif row.get("voucher_type") == "Payment Entry":
			refs = payment_references.get(row.get("voucher_no"), [])
			row["sales_invoice"] = _names(ref.reference_name for ref in refs)
			all_links = [links.get(ref.reference_name, {}) for ref in refs]
			row["related_sales_orders"] = _names(order for bucket in all_links for order in bucket.get("sales_orders", set()))
			row["related_delivery_notes"] = _names(note for bucket in all_links for note in bucket.get("delivery_notes", set()))
			row["customer_po_no"] = _names(bucket.get("customer_po_no") for bucket in all_links)
			row["payment_entry"] = row.get("voucher_no")
			row.update({"original_amount": 0, "settled_amount": 0, "outstanding_amount": 0,
				"billing_status": "", "payment_status": "未分配" if not refs else "部分收款"})
	return rows


def get_customer_ledger_snapshot(company, customer, from_date, to_date):
	"""Return customer receivable movements in company currency without writing data."""
	_validate_filters(company, customer, from_date, to_date)
	from_date, to_date = getdate(from_date), getdate(to_date)
	entries = frappe.get_all(
		"GL Entry",
		filters={
			"company": company,
			"party_type": "Customer",
			"party": customer,
			"posting_date": ["<=", to_date],
			"is_cancelled": 0,
		},
		fields=[
			"name", "creation", "modified", "posting_date", "voucher_type", "voucher_no",
			"account", "remarks", "debit", "credit",
		],
		order_by="posting_date asc, creation asc, name asc",
	)
	opening = sum(
		flt(row.debit) - flt(row.credit)
		for row in entries
		if getdate(row.posting_date) < from_date
	)
	period_entries = [row for row in entries if getdate(row.posting_date) >= from_date]
	for row in period_entries:
		if row.voucher_type and row.voucher_no and not frappe.has_permission(
			row.voucher_type, ptype="read", doc=row.voucher_no
		):
			frappe.throw(_("没有读取来源凭证 {0} {1} 的权限，不能生成余额不完整的对账单").format(
				row.voucher_type, row.voucher_no
			))
	balance, rows = opening, []
	for row in period_entries:
		balance += flt(row.debit) - flt(row.credit)
		rows.append({
			"line_source": "Ledger",
			"match_status": "Matched",
			"transaction_category": _transaction_category(row.voucher_type, row.debit, row.credit),
			"gl_entry": row.name,
			"posting_date": row.posting_date,
			"voucher_type": row.voucher_type,
			"voucher_no": row.voucher_no,
			"account": row.account,
			"remarks": row.remarks,
			"debit": flt(row.debit),
			"credit": flt(row.credit),
			"balance": balance,
			"reconciling_amount": flt(row.debit) - flt(row.credit),
		})
	enrich_customer_ledger_rows(rows, to_date)
	opening_documents = get_opening_customer_documents(company, customer, from_date)
	order_billing_rows = get_customer_order_billing_details(company, customer, from_date, to_date)
	opening_document_total = sum(flt(doc["outstanding_amount"]) for doc in opening_documents["documents"])
	opening_documents["adjustment"] = flt(opening) - opening_document_total
	period_debit = sum(flt(row.debit) for row in period_entries)
	period_credit = sum(flt(row.credit) for row in period_entries)
	period_balance = period_debit - period_credit
	line_original_total = sum(flt(row.get("original_amount")) for row in rows)
	line_settled_total = sum(flt(row.get("settled_amount")) for row in rows)
	return {
		"company": company,
		"customer": customer,
		"from_date": from_date,
		"to_date": to_date,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"opening_balance": opening,
		"period_debit": period_debit,
		"period_credit": period_credit,
		"period_balance": period_balance,
		"closing_balance": opening + period_balance,
		"voucher_count": len({(row.voucher_type, row.voucher_no) for row in period_entries}),
		"row_count": len(rows),
	"snapshot_key": _snapshot_key(company, customer, from_date, to_date, entries + [
			frappe._dict(name=f"opening:{doc['sales_invoice']}", modified=str(doc["outstanding_amount"]), debit=0, credit=0)
			for doc in opening_documents["documents"]
		] + [
			frappe._dict(
				name=f"order:{row.get('sales_order')}:{row.get('item_code')}",
				modified=json.dumps(row, sort_keys=True, default=str),
				debit=0,
				credit=0,
			)
			for row in order_billing_rows
		]),
		"opening_documents": opening_documents["documents"],
		"opening_document_count": len(opening_documents["documents"]),
		"opening_document_total": opening_document_total,
		"opening_adjustment": flt(opening_documents["adjustment"]),
		"order_billing_rows": order_billing_rows,
		"line_original_total": line_original_total,
		"line_settled_total": line_settled_total,
		"line_outstanding_total": line_original_total - line_settled_total,
		"order_billing_count": len(order_billing_rows),
		"rows": rows,
	}


@frappe.whitelist()
def preview_customer_account_statement(company, customer, from_date, to_date):
	frappe.only_for(RECONCILIATION_USERS)
	data = get_customer_ledger_snapshot(company, customer, from_date, to_date)
	if not data["rows"] and not data["opening_balance"]:
		frappe.throw(_("该客户在所选期间没有往来账记录"))
	return data


def get_customer_delivery_rows(company, customer, from_date, to_date):
	_validate_filters(company, customer, from_date, to_date)
	docs = frappe.get_all(
		"Delivery Note",
		filters={
			"company": company,
			"customer": customer,
			"posting_date": ["between", [from_date, to_date]],
			"docstatus": 1,
			"is_return": 0,
			"custom_china_settlement_mode": "对账结算后确认应收",
		},
		fields=["name", "posting_date", "currency"],
		order_by="posting_date asc, name asc",
	)
	rows, currencies, excluded = [], set(), []
	for header in docs:
		if not frappe.has_permission("Delivery Note", ptype="read", doc=header.name):
			excluded.append({"name": header.name, "reason": _("无读取权限")})
			continue
		doc = frappe.get_doc("Delivery Note", header.name)
		currencies.add(doc.currency)
		for item in doc.items:
			amount = flt(item.amount)
			rows.append({
				"line_source": "Ledger",
				"match_status": "Matched",
				"posting_date": doc.posting_date,
				"voucher_type": "Delivery Note",
				"voucher_no": doc.name,
				"source_detail_name": item.name,
				"order_no": item.against_sales_order,
				"delivery_note": doc.name,
				"item_code": item.item_code,
				"item_name": item.item_name,
				"uom": item.uom or item.stock_uom,
				"qty": item.qty,
				"rate": item.rate,
				"amount": amount,
				"currency": doc.currency,
				"remarks": f"{item.item_code or ''} {item.item_name or ''}".strip(),
				"debit": amount if amount >= 0 else 0,
				"credit": abs(amount) if amount < 0 else 0,
				"balance": amount,
				"reconciling_amount": amount,
			})
	if len(currencies) > 1:
		frappe.throw(_("对账期间内存在多个币种，请拆分生成对账单"))
	return {"rows": rows, "currency": next(iter(currencies), None), "excluded": excluded}


@frappe.whitelist()
def preview_customer_reconciliation_statement(company, customer, from_date, to_date):
	data = get_customer_delivery_rows(company, customer, from_date, to_date)
	if not data["rows"]:
		frappe.throw(_("该客户在所选期间没有启用对账结算的已提交送货单"))
	return {
		"company": company,
		"customer": customer,
		"from_date": from_date,
		"to_date": to_date,
		"currency": data["currency"],
		"row_count": len(data["rows"]),
		"document_count": len({row["voucher_no"] for row in data["rows"]}),
		"total": sum(flt(row["balance"]) for row in data["rows"]),
		"rows": data["rows"],
		"excluded": data["excluded"],
	}


@frappe.whitelist()
def load_customer_reconciliation_lines(company, customer, from_date, to_date):
	return preview_customer_reconciliation_statement(company, customer, from_date, to_date)
