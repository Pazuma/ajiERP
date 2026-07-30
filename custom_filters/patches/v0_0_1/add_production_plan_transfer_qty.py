import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Material Request Plan Item": [
				{
					"fieldname": "custom_transfer_qty",
					"label": "Transfer Qty",
					"fieldtype": "Float",
					"read_only": 1,
					"in_list_view": 1,
					"insert_after": "quantity",
					"precision": "2",
				}
			]
		},
		update=True,
	)
	frappe.clear_cache(doctype="Material Request Plan Item")
