"""Compact Supplier details layout, preserving all existing fields."""

import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def ensure_layout():
	make_property_setter("Supplier", "supplier_name_in_arabic", "label", "供应商阿拉伯语名称", "Data")
	definitions = [
		("custom_supplier_basic_section", "Section Break", "基础信息"),
		("custom_supplier_basic_col2", "Column Break", ""),
		("custom_supplier_basic_col3", "Column Break", ""),
		("custom_supplier_notes_section", "Section Break", "联系与地址"),
		("custom_supplier_review_section", "Section Break", "采购回顾"),
		("custom_supplier_review_col2", "Column Break", ""),
		("custom_supplier_review_col3", "Column Break", ""),
		("custom_supplier_remaining_section", "Section Break", "其他信息"),
	]
	create_custom_fields({"Supplier": [
		{"fieldname": name, "fieldtype": kind, "label": label, "insert_after": "supplier_name",
		 "hidden": int(name in {"custom_supplier_notes_section", "custom_supplier_remaining_section"})}
		for name, kind, label in definitions
	] + [{
		"fieldname": "custom_purchase_employee",
		"fieldtype": "Link",
		"label": "采购人员",
		"options": "Employee",
		"insert_after": "supplier_group",
	}]}, update=True)
	meta = frappe.get_meta("Supplier", cached=False)
	order = [f.fieldname for f in meta.fields]
	block = [
		"custom_supplier_basic_section", "supplier_name", "supplier_group", "custom_purchase_employee",
		"custom_supplier_basic_col2", "custom_supplier_code", "custom_cooperation_status",
		"custom_supplier_basic_col3", "supplier_type", "country", "is_transporter",
		"custom_supplier_notes_section", "custom_supplier_remarks",
		"custom_supplier_review_section", "custom_review_total_orders", "custom_review_delayed_orders", "custom_review_average_delay_days",
		"custom_supplier_review_col2", "custom_review_on_time_orders", "custom_supplier_rating", "custom_review_rating",
		"custom_supplier_review_col3", "custom_review_on_time_rate", "custom_rating_standard",
		"custom_supplier_remaining_section",
	]
	block = [name for name in block if name in order]
	remaining = [name for name in order if name not in block]
	# Keep the series and hidden parser configuration before the visible layout.
	prefix = [name for name in remaining if name in {
		"naming_series", "custom_quote_column_mapping", "custom_quote_item_mapping"
	}]
	final = prefix + block + [name for name in remaining if name not in prefix]
	make_property_setter("Supplier", None, "field_order", json.dumps(final), "JSON", for_doctype=True)
	frappe.clear_cache(doctype="Supplier")
