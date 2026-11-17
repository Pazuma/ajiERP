"""Read-only Sales Order product data used by the Sales Order list view.

The list view asks for a batch of small summaries.  Full item rows are only
loaded after the user hovers a product cell, so opening a long list does not
create one request per order.
"""

import json

import frappe
from frappe import _


MAX_SUMMARY_ORDERS = 500
ITEM_FIELDS = ("item_code", "item_name", "description", "qty", "uom", "stock_uom")
OPTIONAL_ITEM_FIELDS = ("custom_product", "custom_specifications")


def _parse_sales_order_names(value, *, limit=MAX_SUMMARY_ORDERS):
	"""Normalize a JSON/list order selection without accepting arbitrary values."""
	if isinstance(value, str):
		try:
			value = frappe.parse_json(value)
		except (TypeError, ValueError, json.JSONDecodeError):
			frappe.throw(_("销售订单参数无效。"), frappe.ValidationError)

	if value is None:
		return []
	if not isinstance(value, (list, tuple)):
		frappe.throw(_("销售订单参数必须是列表。"), frappe.ValidationError)

	names = []
	seen = set()
	for value_item in value:
		name = str(value_item or "").strip()
		if name and name not in seen:
			names.append(name)
			seen.add(name)

	if len(names) > limit:
		frappe.throw(_("一次最多查询 {0} 个销售订单。").format(limit), frappe.ValidationError)
	return names


def _get_allowed_sales_orders(names):
	"""Return only existing orders readable by the current user."""
	allowed = []
	for name in names:
		if not frappe.db.exists("Sales Order", name):
			continue
		try:
			if frappe.has_permission("Sales Order", ptype="read", doc=name):
				allowed.append(name)
		except (frappe.DoesNotExistError, frappe.PermissionError):
			# Do not reveal whether a name exists when the user cannot read it.
			continue
	return allowed


def _get_item_fields():
	fields = list(ITEM_FIELDS)
	meta = frappe.get_meta("Sales Order Item")
	for fieldname in OPTIONAL_ITEM_FIELDS:
		if meta.has_field(fieldname):
			fields.append(fieldname)
	return fields


def _get_item_rows(sales_orders):
	if not sales_orders:
		return []

	return frappe.get_all(
		"Sales Order Item",
		filters={
			"parent": ["in", sales_orders],
			"parenttype": "Sales Order",
		},
		fields=["parent", "idx", *_get_item_fields()],
		order_by="parent asc, idx asc",
	)


def _item_payload(row):
	"""Keep the API response to the fields needed by the product popover."""
	return {
		"item_code": row.get("item_code") or "",
		"item_name": (
			row.get("custom_product")
			or row.get("item_name")
			or row.get("item_code")
			or "-"
		),
		"description": row.get("custom_specifications") or row.get("description") or "",
		"qty": row.get("qty"),
		"uom": row.get("uom") or row.get("stock_uom") or "",
	}


def _group_items(rows):
	items_by_order = {}
	for row in rows:
		items_by_order.setdefault(row.parent, []).append(_item_payload(row))
	return items_by_order


@frappe.whitelist()
def get_sales_order_product_summaries(sales_orders):
	"""Return the first two product names for each readable order in a batch."""
	names = _parse_sales_order_names(sales_orders)
	allowed = _get_allowed_sales_orders(names)
	items_by_order = _group_items(_get_item_rows(allowed))

	result = {}
	for name in allowed:
		items = items_by_order.get(name, [])
		result[name] = {
			"sales_products": [item["item_name"] for item in items[:2]],
			"sales_product_count": len(items),
			"sales_product_has_more": len(items) > 2,
		}
	return result


@frappe.whitelist()
def get_sales_order_products(sales_order):
	"""Return all product rows for one order after its read permission is checked."""
	names = _parse_sales_order_names([sales_order], limit=1)
	if not names or not frappe.db.exists("Sales Order", names[0]):
		frappe.throw(_("销售订单不存在或无权访问。"), frappe.DoesNotExistError)

	frappe.has_permission("Sales Order", ptype="read", doc=names[0], throw=True)
	items = _group_items(_get_item_rows(names)).get(names[0], [])
	return {"sales_order": names[0], "items": items}
