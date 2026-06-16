import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "dingtalk_user_id",
					"fieldtype": "Data",
					"insert_after": "third_party_authentication",
					"label": "DingTalk UserId",
					"description": "DingTalk user ID used by Draft Notification Rules when sending DingTalk private chat messages.",
					"in_standard_filter": 1,
				},
			]
		},
		update=True,
	)
	frappe.clear_cache(doctype="User")
