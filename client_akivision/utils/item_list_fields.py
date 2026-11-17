"""Metadata for the read-only, dynamically rendered warehouse stock column."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_item_list_fields():
	create_custom_fields({"Item": [{
		"fieldname": "warehouse_stock_summary",
		"label": "仓库物料",
		"fieldtype": "Data",
		"insert_after": "stock_uom",
		"read_only": 1,
		"hidden": 1,
		"no_copy": 1,
		"description": "列表实时展示各仓库实际库存，不保存库存余额。",
	}]})
