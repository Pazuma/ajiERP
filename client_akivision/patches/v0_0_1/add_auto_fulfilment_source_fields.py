"""Identify Delivery Notes and Work Orders created by Sales Order auto fulfilment."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	fields = [
		{"fieldname": "custom_auto_fulfilment", "label": "自动履约草稿", "fieldtype": "Check", "read_only": 1, "hidden": 1},
		{"fieldname": "custom_auto_fulfilment_sales_order", "label": "自动履约来源销售订单", "fieldtype": "Link", "options": "Sales Order", "read_only": 1, "hidden": 1},
	]
	create_custom_fields({"Delivery Note": fields, "Work Order": fields}, update=True)
