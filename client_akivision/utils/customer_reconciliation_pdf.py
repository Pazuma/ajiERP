"""Formal customer reconciliation PDF. It never writes accounting or stock data."""

import base64
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from client_akivision.utils.formal_pdf_export import parse_names, read_doc, render_pdf

ALLOWED = {"Sales Order": ("transaction_date", "items"), "Delivery Note": ("posting_date", "items")}


def _customer_account_statement_logo_uri():
	"""Embed the statement logo so PDF rendering does not depend on file access."""
	path = Path(frappe.get_app_path("client_akivision", "public", "images", "customer_account_statement_logo_uniform.png"))
	if not path.exists():
		return ""
	return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _build(source_doctype, document_names):
	if source_doctype not in ALLOWED:
		frappe.throw(_("仅支持销售订单或送货单生成客户对账单。"))
	docs = [read_doc(source_doctype, name) for name in parse_names(document_names)]
	docs = [doc for doc in docs if doc.docstatus == 1 and doc.status != "Cancelled"]
	if not docs:
		frappe.throw(_("没有符合条件的已提交单据。"))
	company, customer, currency = docs[0].company, docs[0].customer, docs[0].currency
	if any(doc.company != company or doc.customer != customer or doc.currency != currency for doc in docs):
		frappe.throw(_("客户对账单只能选择同一公司、客户和币种的单据，请拆分生成。"))
	date_field, child_field = ALLOWED[source_doctype]
	rows, total, dates = [], 0, []
	for doc in docs:
		dates.append(str(doc.get(date_field) or ""))
		for item in doc.get(child_field) or []:
			qty = item.qty if source_doctype == "Sales Order" else item.get("qty")
			amount = flt(item.amount)
			total += amount
			rows.append({"date": doc.get(date_field), "document_no": doc.name, "item_code": item.item_code, "item_name": item.item_name or item.item_code, "uom": item.uom or item.stock_uom, "qty": qty, "rate": item.rate, "amount": amount, "delivery_note": doc.name if source_doctype == "Delivery Note" else "", "remarks": item.get("description") or ""})
	if not rows:
		frappe.throw(_("所选单据没有可对账的明细。"))
	company_name = frappe.db.get_value("Company", company, "company_name") or company
	return {"company": company, "company_name": company_name, "customer": frappe.db.get_value("Customer", customer, "customer_name") or customer, "currency": currency, "source_doctype": source_doctype, "rows": rows, "total": total, "start_date": min(dates), "end_date": max(dates), "payment_note": "已付款、未付款金额以财务确认为准"}


@frappe.whitelist()
def preview_customer_reconciliation(source_doctype, document_names):
	data = _build(source_doctype, document_names)
	return {key: data[key] for key in ("company_name", "customer", "currency", "total", "start_date", "end_date", "payment_note")} | {"row_count": len(data["rows"])}


@frappe.whitelist()
def download_customer_reconciliation_pdf(source_doctype, document_names):
	data = _build(source_doctype, document_names)
	content = render_pdf("templates/customer_reconciliation_pdf.html", data, "Landscape")
	from frappe.desk.utils import provide_binary_file
	provide_binary_file(f"客户对账单-{data['customer']}-{data['start_date']}至{data['end_date']}", "pdf", content)


@frappe.whitelist()
def download_saved_customer_reconciliation_statement(statement_name):
	"""Export a saved China Reconciliation Statement snapshot."""
	statement = read_doc("China Reconciliation Statement", statement_name)
	if statement.statement_type != "Customer":
		frappe.throw(_("只有客户对账单可以导出客户对账 PDF。"))
	if statement.get("statement_basis") == "Ledger":
		return _download_saved_customer_account_statement(statement)
	rows = []
	for line in statement.lines:
		rows.append({
			"date": line.posting_date,
			"document_no": line.order_no or line.voucher_no,
			"item_code": line.item_code or "",
			"item_name": line.item_name or line.remarks or "",
			"uom": line.uom or "",
			"qty": line.qty or "",
			"rate": line.rate or "",
			"amount": line.amount if line.amount is not None else line.balance,
			"delivery_note": line.delivery_note or (line.voucher_no if line.voucher_type == "Delivery Note" else ""),
			"remarks": line.remarks or "",
		})
	if not rows:
		frappe.throw(_("对账单没有可导出的明细。"))
	company_name = frappe.db.get_value("Company", statement.company, "company_name") or statement.company
	data = {
		"company_name": company_name,
		"customer": frappe.db.get_value("Customer", statement.party, "customer_name") or statement.party,
		"currency": statement.get("currency") or next((line.currency for line in statement.lines if line.currency), ""),
		"source_doctype": "China Reconciliation Statement",
		"rows": rows,
		"total": sum(flt(row["amount"]) for row in rows),
		"start_date": statement.from_date,
		"end_date": statement.to_date,
		"payment_note": "已付款、未付款金额以财务确认为准",
	}
	content = render_pdf("templates/customer_reconciliation_pdf.html", data, "Landscape")
	from frappe.desk.utils import provide_binary_file
	provide_binary_file(f"客户对账单-{data['customer']}-{data['start_date']}至{data['end_date']}", "pdf", content)


def _download_saved_customer_account_statement(statement):
	rows = [
		{
			"date": line.posting_date,
			"category": line.transaction_category or "",
			"voucher_type": line.voucher_type or "",
			"voucher_no": line.voucher_no or "",
			"account": line.account or "",
			"remarks": line.remarks or "",
			"debit": line.debit or 0,
			"credit": line.credit or 0,
			"balance": line.balance or 0,
		}
		for line in statement.lines
	]
	company_name = frappe.db.get_value("Company", statement.company, "company_name") or statement.company
	order_rows = [
		{
			"date": row.order_date,
			"document_no": row.sales_order or "",
			"customer_po_no": row.customer_po_no or "",
			"item_code": row.item_code or "",
			"item_name": row.item_name or "",
			"uom": row.uom or "",
			"ordered_qty": row.ordered_qty or 0,
			"delivered_qty": row.delivered_qty or 0,
			"billed_qty": row.billed_qty or 0,
			"order_amount": row.order_amount or 0,
			"billed_amount": row.billed_amount or 0,
			"paid_amount": row.paid_amount or 0,
			# This layout reconciles the entire order, including its unbilled part.
			"outstanding_amount": flt(row.order_amount) - flt(row.paid_amount),
			"delivery_notes": row.delivery_notes or "",
			"sales_invoices": row.sales_invoices or "",
			"billing_status": row.billing_status or "",
			"payment_status": row.payment_status or "",
			"rate": flt(row.order_amount) / flt(row.ordered_qty) if flt(row.ordered_qty) else 0,
			"remarks": row.get("remarks") or "",
		}
		for row in (statement.get("order_billing_rows") or [])
	]
	if not order_rows:
		frappe.throw(_("本对账单没有订单明细，无法生成产品明细格式的客户对账单。请先生成订单账单明细。"))
	opening_rows = [
		{
			"date": row.posting_date,
			"document_no": row.sales_invoice or "",
			"original_amount": row.original_amount or 0,
			"settled_amount": row.settled_amount or 0,
			"outstanding_amount": row.outstanding_amount or 0,
			"related_sales_orders": row.related_sales_orders or "",
			"related_delivery_notes": row.related_delivery_notes or "",
		}
		for row in (statement.get("opening_documents") or [])
	]
	order_amount = sum(flt(row["order_amount"]) for row in order_rows)
	billed_amount = sum(flt(row["billed_amount"]) for row in order_rows)
	paid_amount = sum(flt(row["paid_amount"]) for row in order_rows)
	outstanding_amount = sum(flt(row["outstanding_amount"]) for row in order_rows)
	data = {
		"company_name": company_name,
		"customer": frappe.db.get_value("Customer", statement.party, "customer_name") or statement.party,
		"currency": statement.currency or frappe.get_cached_value("Company", statement.company, "default_currency"),
		"statement_name": statement.name,
		"version": statement.version or 1,
		"export_date": nowdate(),
		"statement_logo_data_uri": _customer_account_statement_logo_uri(),
		"rows": rows,
		"row_count": len(rows),
		"voucher_count": len({(row["voucher_type"], row["voucher_no"]) for row in rows}),
		"opening_balance": statement.opening_balance or 0,
		"period_debit": statement.period_debit or 0,
		"period_credit": statement.period_credit or 0,
		"closing_balance": statement.closing_balance or 0,
		"period_balance": statement.get("period_balance") if statement.get("period_balance") is not None else flt(statement.period_debit) - flt(statement.period_credit),
		"order_rows": order_rows,
		"opening_rows": opening_rows,
		"order_billing_count": len(order_rows),
		"order_amount": order_amount,
		"billed_amount": billed_amount,
		"paid_amount": paid_amount,
		"outstanding_amount": outstanding_amount,
		"unbilled_amount": order_amount - billed_amount,
		"start_date": statement.from_date,
		"end_date": statement.to_date,
	}
	data.update(_statement_bank_details(statement.company))
	content = render_pdf("templates/customer_account_statement_pdf.html", data, "Landscape")
	from frappe.desk.utils import provide_binary_file
	provide_binary_file(f"客户往来对账单-{data['customer']}-{data['start_date']}至{data['end_date']}", "pdf", content)


def _statement_bank_details(company):
	"""Only print the company's configured account; never guess bank details."""
	accounts = frappe.get_list("Bank Account", filters={"company": company,
		"is_company_account": 1, "is_default": 1, "disabled": 0}, fields=["name"], limit_page_length=2)
	if len(accounts) != 1:
		return {"bank_name": "", "bank_account_no": ""}
	account = read_doc("Bank Account", accounts[0].name)
	if not account.is_company_account or account.company != company:
		return {"bank_name": "", "bank_account_no": ""}
	return {"bank_name": account.bank or "", "bank_account_no": account.bank_account_no or ""}
