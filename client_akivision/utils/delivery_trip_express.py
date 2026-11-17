import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def ensure_schema():
	create_custom_fields(
		{
			"Delivery Trip": [
				{
					"fieldname": "custom_express_info_section",
					"label": "快递信息",
					"fieldtype": "Section Break",
					"insert_after": "departure_time",
				},
				{
					"fieldname": "custom_express_company",
					"label": "快递公司",
					"fieldtype": "Data",
					"insert_after": "custom_express_info_section",
				},
				{
					"fieldname": "custom_express_remarks",
					"label": "备注",
					"fieldtype": "Small Text",
					"insert_after": "custom_express_company",
				},
				{
					"fieldname": "custom_express_column",
					"fieldtype": "Column Break",
					"insert_after": "custom_express_remarks",
				},
				{
					"fieldname": "custom_tracking_number",
					"label": "快递单号",
					"fieldtype": "Data",
					"insert_after": "custom_express_column",
				},
			],
		},
		update=True,
	)
	for fieldname, insert_after in (
		("custom_express_remarks", "custom_express_company"),
		("custom_express_column", "custom_express_remarks"),
		("custom_tracking_number", "custom_express_column"),
	):
		frappe.db.set_value(
			"Custom Field", {"dt": "Delivery Trip", "fieldname": fieldname},
			"insert_after", insert_after, update_modified=False,
		)
	for fieldname, property_name in (
		("section_break_3", "hidden"),
		("vehicle", "reqd"),
		("departure_time", "reqd"),
	):
		make_property_setter(
			"Delivery Trip", fieldname, property_name, 1 if property_name == "hidden" else 0,
			"Check", validate_fields_for_doctype=False,
		)
	frappe.db.updatedb("Delivery Trip")
	frappe.clear_cache(doctype="Delivery Trip")
