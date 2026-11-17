import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


DOCTYPE = "Data Import"


def ensure_data_import_customization():
	"""Install the guided Data Import layout without modifying Frappe core."""
	create_custom_fields(
		{
			DOCTYPE: [
				{
					"fieldname": "custom_import_setup_guide",
					"fieldtype": "HTML",
					"label": "Import Setup Guide",
					"insert_after": "import_type",
				},
				{
					"fieldname": "custom_advanced_settings_section",
					"fieldtype": "Section Break",
					"label": "Advanced Settings",
					"collapsible": 1,
					"insert_after": "column_break_5",
				},
				{
					"fieldname": "custom_post_save_guide",
					"fieldtype": "HTML",
					"label": "Next Step",
					"depends_on": "eval:!doc.__islocal",
					"insert_after": "submit_after_import",
				},
			]
		},
		update=True,
	)

	for fieldname, property_name, value, property_type in (
		("reference_doctype", "label", "Import Object", "Data"),
		(
			"reference_doctype",
			"description",
			"Choose the document or master data that this file should import into.",
			"Text",
		),
		("import_type", "label", "Import Method", "Data"),
		(
			"import_type",
			"description",
			"Choose whether the file should create new records or update records that already exist.",
			"Text",
		),
	):
		set_property_if_changed(fieldname, property_name, value, property_type)

	meta = frappe.get_meta(DOCTYPE, cached=False)
	existing_order = [field.fieldname for field in meta.fields]
	preferred_order = [
		"custom_import_setup_guide",
		"reference_doctype",
		"import_type",
		"column_break_5",
		"custom_advanced_settings_section",
		"use_csv_sniffer",
		"custom_delimiters",
		"delimiter_options",
		"mute_emails",
		"submit_after_import",
		"custom_post_save_guide",
		"download_template",
		"import_file",
		"payload_count",
		"html_5",
		"google_sheets_url",
		"refresh_google_sheet",
		"status",
		"template_options",
		"import_warnings_section",
		"template_warnings",
		"import_warnings",
		"section_import_preview",
		"import_preview",
		"import_log_section",
		"show_failed_logs",
		"import_log_preview",
	]
	field_order = [name for name in preferred_order if name in existing_order]
	field_order.extend(name for name in existing_order if name not in field_order)
	set_property_if_changed(None, "field_order", json.dumps(field_order), "JSON", for_doctype=True)
	frappe.clear_cache(doctype=DOCTYPE)


def set_property_if_changed(fieldname, property_name, value, property_type, for_doctype=False):
	property_setter_name = f"{DOCTYPE}-{fieldname or 'main'}-{property_name}"
	current_value = frappe.db.get_value("Property Setter", property_setter_name, "value")
	if current_value == str(value):
		return

	make_property_setter(
		DOCTYPE,
		fieldname,
		property_name,
		value,
		property_type,
		for_doctype=for_doctype,
	)
