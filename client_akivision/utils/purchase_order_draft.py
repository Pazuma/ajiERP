"""Turn Purchase Recommendation rows into Purchase Order drafts."""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from client_akivision.client_akivision.doctype.supplier_quote_import.supplier_quote_import import (
	_default_warehouse,
)


@frappe.whitelist()
def add_item_to_supplier_po_draft(
	supplier,
	item_code,
	qty,
	rate,
	company,
	payment_terms=None,
	material_request=None,
	material_request_item=None,
	purchase_comparison=None,
	warehouse=None,
):
	"""Add the recommended item to the supplier's open draft PO, or create one.

	An already-submitted draft is never touched: only docstatus=0 orders are
	reused, otherwise a fresh draft is created. Optional MR line references are
	carried onto the PO item so the Material Request tracks ordering natively,
	and the PO links back to the originating Purchase Comparison. An explicit
	warehouse wins over the default warehouse chain.
	"""
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("没有创建采购订单的权限"), frappe.PermissionError)
	qty = flt(qty)
	rate = flt(rate)
	if qty <= 0:
		frappe.throw(_("推荐数量必须大于零"))
	if rate < 0:
		frappe.throw(_("推荐单价不能为负数"))

	draft_filters = {"supplier": supplier, "company": company, "docstatus": 0}
	if purchase_comparison:
		# Comparison-generated POs only merge into drafts of the same comparison,
		# so unrelated open drafts are never polluted.
		draft_filters["custom_purchase_comparison"] = purchase_comparison
	draft_name = frappe.db.get_value(
		"Purchase Order",
		draft_filters,
		"name",
		order_by="creation desc",
	)
	if draft_name:
		po = frappe.get_doc("Purchase Order", draft_name)
		if not po.has_permission("write"):
			frappe.throw(_("没有修改采购订单 {0} 的权限").format(draft_name), frappe.PermissionError)
		if purchase_comparison and po.get("custom_purchase_comparison") != purchase_comparison:
			po.custom_purchase_comparison = purchase_comparison
		action = _append_item(po, item_code, qty, rate, material_request, material_request_item, warehouse)
		po.save()
		return {"purchase_order": po.name, "action": action}

	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"supplier": supplier,
			"company": company,
			"transaction_date": getdate(),
			"payment_terms": payment_terms or None,
			"custom_purchase_comparison": purchase_comparison,
			"items": [_make_item(item_code, qty, rate, company, material_request, material_request_item, warehouse)],
		}
	)
	po.insert()
	return {"purchase_order": po.name, "action": "created"}


def _append_item(po, item_code, qty, rate, material_request=None, material_request_item=None, warehouse=None):
	"""Merge the qty into an existing line for the same item, else append a line.

	Lines linked to a different Material Request item are never merged, so
	line-level MR traceability stays intact.
	"""
	for row in po.items:
		if row.item_code == item_code and (row.get("material_request_item") or None) == (
			material_request_item or None
		):
			row.qty = flt(row.qty) + qty
			row.rate = rate
			return "merged"
	po.append("items", _make_item(item_code, qty, rate, po.company, material_request, material_request_item, warehouse))
	return "updated"


def _make_item(item_code, qty, rate, company, material_request=None, material_request_item=None, warehouse=None):
	item = {
		"item_code": item_code,
		"qty": qty,
		"rate": rate,
		"uom": frappe.db.get_value("Item", item_code, "stock_uom"),
		"warehouse": warehouse or _default_warehouse(item_code, company),
		"schedule_date": getdate(),
	}
	if material_request:
		item["material_request"] = material_request
	if material_request_item:
		item["material_request_item"] = material_request_item
	return item
