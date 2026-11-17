"""Add a read-only purchasing-tab display for historical purchase cost."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate


def ensure_schema():
	create_custom_fields({"Item": [{
		"fieldname": "custom_purchase_average_cost_html",
		"fieldtype": "HTML",
		"label": "历史采购平均单价",
		"insert_after": "supplier_items",
		"description": "按已提交采购收货及退货统计；仅供成本估算，不改变库存估值。",
	}]}, update=True)
	frappe.clear_cache(doctype="Item")


@frappe.whitelist()
def get_item_selling_prices(item_code):
	"""Pricing-tab-only view; does not change ERPNext's Item Price API."""
	frappe.has_permission("Item", doc=item_code, ptype="read", throw=True)
	if not frappe.has_permission("Item Price", "read"):
		frappe.throw(_("缺少物料价格读取权限"), frappe.PermissionError)
	prices = frappe.get_list(
		"Item Price",
		filters={"item_code": item_code, "selling": 1, "docstatus": ("!=", 2)},
		or_filters=[["valid_upto", "is", "not set"], ["valid_upto", ">=", getdate()]],
		fields=["name", "price_list", "price_list_rate", "currency", "uom", "customer", "supplier", "buying", "selling", "valid_upto"],
		order_by="price_list asc", limit_page_length=11,
	)
	return {"prices": prices[:10], "has_more": len(prices) > 10}
