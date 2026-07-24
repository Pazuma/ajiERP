"""Turn Purchase Recommendation rows into Purchase Order drafts."""

import frappe
from frappe import _
from frappe.utils import flt, today

from client_akivision.client_akivision.doctype.supplier_quote_import.supplier_quote_import import (
	_default_warehouse,
)


@frappe.whitelist()
def add_item_to_supplier_po_draft(supplier, item_code, qty, rate, company, payment_terms=None):
	"""Add the recommended item to the supplier's open draft PO, or create one.

	An already-submitted draft is never touched: only docstatus=0 orders are
	reused, otherwise a fresh draft is created.
	"""
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("没有创建采购订单的权限"), frappe.PermissionError)
	qty = flt(qty)
	rate = flt(rate)
	if qty <= 0:
		frappe.throw(_("推荐数量必须大于零"))
	if rate < 0:
		frappe.throw(_("推荐单价不能为负数"))

	draft_name = frappe.db.get_value(
		"Purchase Order",
		{"supplier": supplier, "company": company, "docstatus": 0},
		"name",
		order_by="creation desc",
	)
	if draft_name:
		po = frappe.get_doc("Purchase Order", draft_name)
		if not po.has_permission("write"):
			frappe.throw(_("没有修改采购订单 {0} 的权限").format(draft_name), frappe.PermissionError)
		action = _append_item(po, item_code, qty, rate)
		po.save()
		return {"purchase_order": po.name, "action": action}

	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": supplier,
			"company": company,
			"transaction_date": today(),
			"payment_terms": payment_terms or None,
			"items": [_make_item(item_code, qty, rate, company)],
		}
	)
	po.insert()
	return {"purchase_order": po.name, "action": "created"}


def _append_item(po, item_code, qty, rate):
	"""Merge the qty into an existing line for the same item, else append a line."""
	for row in po.items:
		if row.item_code == item_code:
			row.qty = flt(row.qty) + qty
			row.rate = rate
			return "merged"
	po.append("items", _make_item(item_code, qty, rate, po.company))
	return "updated"


def _make_item(item_code, qty, rate, company):
	return {
		"item_code": item_code,
		"qty": qty,
		"rate": rate,
		"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
		"warehouse": _default_warehouse(item_code, company),
		"schedule_date": today(),
	}
