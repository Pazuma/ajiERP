import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_migrate():
	"""Create custom fields owned by custom_filters (idempotent)."""
	create_custom_fields(
		{
			"Buying Settings": [
				{
					"fieldname": "custom_supplier_quotation_warehouse",
					"fieldtype": "Link",
					"label": "Default Supplier Quotation Warehouse",
					"options": "Warehouse",
					"insert_after": "supplier_group",
				}
			]
		},
		update=True,
	)
