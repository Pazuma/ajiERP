"""Keep party fields available in the form but out of the accounting grid."""

import frappe


def execute():
	for fieldname in ("party_type", "party"):
		filters = {
			"doctype_or_field": "DocField",
			"doc_type": "Journal Entry Account",
			"field_name": fieldname,
			"property": "in_list_view",
		}
		name = frappe.db.exists("Property Setter", filters)
		if name:
			if frappe.db.get_value("Property Setter", name, "value") != "0":
				frappe.db.set_value("Property Setter", name, "value", "0", update_modified=False)
		else:
			frappe.get_doc(
				{
					"doctype": "Property Setter",
					**filters,
					"value": "0",
					"property_type": "Check",
					"is_system_generated": 1,
				}
			).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Journal Entry Account")
