"""Ensure Supplier form fields declared by the app exist on every site."""

import json

import frappe


def ensure_schema():
	path = frappe.get_app_path("client_akivision", "config", "excel_form_fields.json")
	with open(path, encoding="utf-8") as source:
		config = json.load(source)

	custom_fields = config.get("custom_fields", {})
	for doctype in ("Customer", "Supplier"):
		fields = custom_fields.get(doctype, [])
		if not fields:
			continue
		from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

		create_custom_fields({doctype: fields}, update=True)

	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for setting in config.get("property_setters", []):
		if setting.get("doctype") != "Supplier":
			continue
		make_property_setter(
			"Supplier",
			setting["fieldname"],
			setting["property"],
			setting["value"],
			setting.get("property_type", "Data"),
		)

	frappe.db.updatedb("Supplier")
	frappe.db.updatedb("Customer")
	frappe.clear_cache(doctype="Supplier")
	frappe.clear_cache(doctype="Customer")
