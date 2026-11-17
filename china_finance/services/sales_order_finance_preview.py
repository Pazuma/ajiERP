"""Read-only finance review data for Sales Orders."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


MODE_SETTLEMENT = "对账结算后确认应收"


def _currency_precision(doc):
	return frappe.get_precision("Sales Order", "grand_total") or 2


def _amount(value, precision):
	return flt(value, precision)


def _tax_rows(doc, precision):
	rows = []
	for tax in doc.get("taxes") or []:
		amount = _amount(tax.get("tax_amount"), precision)
		base = _amount(tax.get("tax_amount_after_discount_amount") or doc.get("net_total"), precision)
		rows.append({
			"description": tax.get("description") or tax.get("account_head") or _("未命名税费"),
			"rate": flt(tax.get("rate")),
			"tax_base": base,
			"tax_amount": amount,
			"account": tax.get("account_head"),
			"direction": "贷方" if amount >= 0 else "借方",
			"kind": "税费" if tax.get("category") == "Total" else "其他销售费用",
		})
	return rows


def _income_entries(doc, precision):
	entries = defaultdict(float)
	default_income_account = frappe.get_cached_value("Company", doc.company, "default_income_account") if doc.company else None
	for item in doc.get("items") or []:
		account = item.get("income_account") or default_income_account
		entries[account or _("待财务配置收入科目")] += flt(item.get("amount"))
	return [
		{"account": account, "debit": 0, "credit": _amount(amount, precision), "remark": _("销售收入（预计）")}
		for account, amount in entries.items() if amount
	]


def _expected_entries(doc, tax_rows, precision):
	if doc.get("custom_china_settlement_mode") == MODE_SETTLEMENT:
		return [], _("当前订单采用对账结算后确认应收；完成确认和销售结算后再确认应收。")

	entries = _income_entries(doc, precision)
	tax_total = 0
	for tax in tax_rows:
		if not tax["tax_amount"]:
			continue
		account = tax["account"] or _("待财务配置税费科目")
		amount = abs(tax["tax_amount"])
		entries.append({
			"account": account,
			"debit": amount if tax["tax_amount"] < 0 else 0,
			"credit": amount if tax["tax_amount"] >= 0 else 0,
			"remark": tax["description"],
		})
		tax_total += tax["tax_amount"]

	credit_total = sum(row["credit"] - row["debit"] for row in entries)
	receivable_account = frappe.get_cached_value("Company", doc.company, "default_receivable_account") if doc.company else None
	entries.insert(0, {
		"account": receivable_account or _("待财务配置应收账款科目"),
		"debit": _amount(credit_total, precision),
		"credit": 0,
		"remark": _("应收账款（预计）"),
	})
	return entries, _("在销售发票或系统配置的应收确认节点提交时预计生成。")


def _linked_invoices(sales_order):
	return frappe.db.sql(
		"""SELECT si.name, si.grand_total, si.status
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE sii.sales_order = %(sales_order)s AND si.docstatus = 1
		GROUP BY si.name, si.grand_total, si.status
		ORDER BY si.posting_date DESC, si.name DESC""",
		{"sales_order": sales_order}, as_dict=True,
	)


def _linked_vouchers(invoice_names):
	if not invoice_names:
		return []
	return frappe.get_all(
		"China Accounting Voucher",
		filters={"source_doctype": "Sales Invoice", "source_name": ["in", invoice_names], "docstatus": 1},
		fields=["name", "statutory_number", "source_name"],
		order_by="posting_date desc, name desc",
	)


def build_preview(doc, invoices=None, vouchers=None):
	"""Build a serializable preview without changing the source document."""
	precision = _currency_precision(doc)
	tax_rows = _tax_rows(doc, precision)
	entries, timing_message = _expected_entries(doc, tax_rows, precision)
	net_total = _amount(doc.get("net_total"), precision)
	tax_total = _amount(doc.get("total_taxes_and_charges"), precision)
	grand_total = _amount(doc.get("grand_total"), precision)
	other_charges = _amount(tax_total - sum(row["tax_amount"] for row in tax_rows), precision)
	invoices = invoices if invoices is not None else []
	vouchers = vouchers if vouchers is not None else []
	balance = _amount(net_total + tax_total - grand_total, precision)

	if vouchers:
		status = {"label": _("已生成中国会计凭证"), "indicator": "green", "reason": None}
	elif invoices:
		status = {"label": _("已生成销售发票"), "indicator": "blue", "reason": _("正式凭证以已提交销售发票的凭证快照为准。")}
	elif doc.get("custom_china_settlement_mode") == MODE_SETTLEMENT:
		status = {"label": _("待客户确认/销售结算"), "indicator": "orange", "reason": timing_message}
	else:
		status = {"label": _("预计记账"), "indicator": "gray", "reason": timing_message}

	return {
		"currency": doc.get("currency"),
		"summary": {
			"net_total": net_total,
			"tax_total": tax_total,
			"other_charges": other_charges,
			"grand_total": grand_total,
			"settlement_mode": doc.get("custom_china_settlement_mode") or _("未设置"),
			"settled_amount": _amount(doc.get("custom_china_settled_amount"), precision),
			"balance": balance,
		},
		"tax_rows": tax_rows,
		"expected_entries": entries,
		"timing_message": timing_message,
		"status": status,
		"invoices": invoices,
		"vouchers": vouchers,
	}


@frappe.whitelist()
def get_sales_order_finance_preview(sales_order):
	"""Return finance review data for one Sales Order after read-permission check."""
	from china_finance.services.sales_order_finance_permissions import assert_finance_access
	assert_finance_access(sales_order)
	doc = frappe.get_doc("Sales Order", sales_order)
	doc.check_permission("read")
	invoices = _linked_invoices(doc.name)
	invoices = [row for row in invoices if frappe.has_permission("Sales Invoice", "read", doc=row.name)]
	vouchers = _linked_vouchers([invoice.name for invoice in invoices])
	vouchers = [row for row in vouchers if frappe.has_permission("China Accounting Voucher", "read", doc=row.name)]
	return build_preview(doc, invoices=invoices, vouchers=vouchers)
