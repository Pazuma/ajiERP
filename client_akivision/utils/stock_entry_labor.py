"""Carry work-order labor cost into Manufacture Stock Entries."""

import frappe
from frappe import _
from frappe.utils import flt

LABOR_MARKER = "[人工成本]"


@frappe.whitelist()
def get_work_order_labor_cost(work_order, company):
	if not work_order or not company:
		return None
	total = flt(frappe.db.get_value("Work Order", work_order, "custom_actual_labor_cost"))
	allocated = frappe.db.sql(
		"""SELECT COALESCE(SUM(lct.amount), 0) FROM `tabLanded Cost Taxes and Charges` lct
		INNER JOIN `tabStock Entry` se ON se.name = lct.parent
		WHERE se.work_order = %s AND se.purpose = 'Manufacture' AND se.docstatus = 1
		AND lct.description LIKE %s""", (work_order, f"%{LABOR_MARKER}%"),
	)[0][0]
	amount = max(total - flt(allocated), 0)
	if not amount:
		return None
	currency = frappe.db.get_value("Company", company, "default_currency")
	return {"amount": amount, "base_amount": amount, "exchange_rate": 1, "account_currency": currency, "expense_account": _get_additional_cost_account(company), "description": f"{LABOR_MARKER} {work_order}"}


def apply_work_order_labor_cost(doc, method=None):
	if doc.get("purpose") != "Manufacture" or not doc.get("work_order"):
		return
	work_order = frappe.db.get_value(
		"Work Order",
		doc.work_order,
		["company", "custom_actual_labor_cost", "qty"],
		as_dict=True,
	)
	if not work_order or work_order.company != doc.company:
		return
	total_labor = flt(work_order.custom_actual_labor_cost)
	for row in list(doc.get("additional_costs") or []):
		if LABOR_MARKER in (row.description or ""):
			doc.remove(row)
	if not total_labor:
		return
	allocated = frappe.db.sql(
		"""SELECT COALESCE(SUM(lct.amount), 0)
		FROM `tabLanded Cost Taxes and Charges` lct
		INNER JOIN `tabStock Entry` se ON se.name = lct.parent
		WHERE se.work_order = %s AND se.purpose = 'Manufacture'
		AND se.docstatus = 1 AND lct.description LIKE %s""",
		(doc.work_order, f"%{LABOR_MARKER}%"),
	)[0][0]
	remaining = max(total_labor - flt(allocated), 0)
	if not remaining:
		return
	account = _get_additional_cost_account(doc.company)
	if not account:
		frappe.throw(_("请先在公司设置中维护默认费用科目，才能带入人工成本。"))
	doc.append(
		"additional_costs",
		{
			"expense_account": account,
			"description": f"{LABOR_MARKER} {doc.work_order}",
			"amount": remaining,
			"base_amount": remaining,
			"exchange_rate": 1,
			"account_currency": frappe.db.get_value("Company", doc.company, "default_currency"),
		},
	)


def _get_additional_cost_account(company):
	"""Use the Stock/Manufacturing Settings extra-cost account before company fallback."""
	for doctype in ("Manufacturing Settings", "Stock Settings"):
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		for fieldname in (
				"default_expense_account",
				"default_expense_account_for_stock_entry",
				"default_stock_entry_expense_account",
			):
			if meta.get_field(fieldname):
				value = frappe.db.get_single_value(doctype, fieldname)
				if value:
					return value
		for field in meta.fields:
			if field.fieldtype == "Link" and "expense account" in (field.label or "").lower():
				value = frappe.db.get_single_value(doctype, field.fieldname)
				if value:
					return value
	return (
		frappe.db.get_value("Company", company, "default_operating_cost_account")
		or frappe.db.get_value("Company", company, "default_expense_account")
	)
