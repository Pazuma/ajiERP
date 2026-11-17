"""Simplified Sales Order to Delivery Note mapping helpers."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note


@frappe.whitelist()
def make_simple_delivery_note(source_name, target_doc=None, kwargs=None):
	"""Create a draft Delivery Note while respecting existing draft deliveries."""
	if not source_name:
		frappe.throw(_("Sales Order is required."))

	frappe.has_permission("Delivery Note", ptype="create", throw=True)
	sales_order = frappe.get_doc("Sales Order", source_name)
	sales_order.check_permission("read")

	if sales_order.docstatus != 1:
		frappe.throw(_("Only submitted Sales Orders can create a Delivery Note."))
	if sales_order.status in ("Closed", "On Hold"):
		frappe.throw(_("Sales Order {0} is {1} and cannot create a Delivery Note.").format(source_name, sales_order.status))

	draft_quantities = _get_draft_delivery_quantities(source_name)
	remaining_by_item = {}
	for item in sales_order.items:
		ordered_qty = flt(item.qty)
		delivered_qty = flt(item.delivered_qty)
		draft_qty = flt(draft_quantities.get(item.name))
		remaining_qty = ordered_qty - delivered_qty - draft_qty
		if remaining_qty > 0 or (ordered_qty == 0 and delivered_qty == 0 and draft_qty == 0):
			remaining_by_item[item.name] = remaining_qty

	if not remaining_by_item:
		frappe.throw(
			_("This Sales Order has no remaining quantity to deliver. Check submitted or draft Delivery Notes."),
			title=_("Already Delivered"),
		)

	map_kwargs = frappe.parse_json(kwargs) if isinstance(kwargs, str) else (kwargs or {})
	map_kwargs = dict(map_kwargs)
	map_kwargs["filtered_children"] = list(remaining_by_item)

	target = make_delivery_note(source_name, target_doc, map_kwargs)
	if not target:
		frappe.throw(_("No deliverable items remain on this Sales Order."), title=_("Nothing to Deliver"))

	# ERPNext's standard mapper does not copy our Excel/import extension fields.
	# Keep the delivery header aligned with the submitted Sales Order.
	for fieldname in ("custom_excel_year", "custom_excel_month", "custom_excel_customer_code"):
		if target.meta.has_field(fieldname) and sales_order.meta.has_field(fieldname):
			setattr(target, fieldname, sales_order.get(fieldname))
	if target.meta.has_field("custom_excel_customer_code") and not target.custom_excel_customer_code:
		target.custom_excel_customer_code = sales_order.customer
	if target.meta.has_field("custom_excel_sales_person"):
		target.custom_excel_sales_person = (
			sales_order.get("custom_excel_sales_person")
			or sales_order.get("custom_sales_person")
		or ""
		)
	if target.meta.has_field("custom_excel_customer_name"):
		target.custom_excel_customer_name = sales_order.get("customer_name") or ""
	if target.meta.has_field("custom_sales_order"):
		target.custom_sales_order = sales_order.name

	trimmed = []
	for item in list(target.items):
		so_detail = item.get("so_detail")
		if not so_detail or so_detail not in remaining_by_item:
			continue

		original_qty = flt(item.qty)
		remaining_qty = remaining_by_item[so_detail]
		if original_qty <= remaining_qty:
			continue

		if remaining_qty <= 0:
			target.items.remove(item)
			continue

		item.qty = remaining_qty
		item.stock_qty = remaining_qty * flt(item.conversion_factor or 1)
		trimmed.append(item.item_code)

	if not target.items:
		frappe.throw(
			_("All remaining quantities are already included in draft Delivery Notes."),
			title=_("Delivery Note Already Drafted"),
		)

	# Recalculate dependent quantity, amount, tax, and packed-item fields after trimming.
	target.run_method("set_missing_values")
	target.run_method("calculate_taxes_and_totals")
	if trimmed:
		frappe.msgprint(
			_("Existing draft Delivery Notes were deducted for: {0}.").format(", ".join(sorted(set(trimmed)))),
			title=_("Draft Quantity Deducted"),
			indicator="blue",
		)

	return target


def _get_draft_delivery_quantities(sales_order):
	"""Return draft Delivery Note quantities grouped by Sales Order Item row."""
	rows = frappe.db.sql(
		"""
		SELECT dni.so_detail, SUM(dni.qty) AS draft_qty
		FROM `tabDelivery Note Item` dni
		INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
		WHERE dn.docstatus = 0
		  AND dni.against_sales_order = %(sales_order)s
		  AND dni.so_detail IS NOT NULL
		GROUP BY dni.so_detail
		""",
		{"sales_order": sales_order},
		as_dict=True,
	)
	return defaultdict(float, {row.so_detail: flt(row.draft_qty) for row in rows})
