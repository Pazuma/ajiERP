"""Expose virtual Sales Order list columns to the standard field picker."""

import frappe


def ensure_sales_order_list_fields():
	"""Create metadata for columns rendered by the Sales Order list extension."""
	fields = [
		("sales_products", "销售产品"),
		("custom_order_number", "编号"),
	]
	for fieldname, label in fields:
		custom_field_name = frappe.db.get_value("Custom Field", {"dt": "Sales Order", "fieldname": fieldname})
		if custom_field_name:
			custom_field = frappe.get_doc("Custom Field", custom_field_name)
			changed = False
			for key, value in {"label": label, "in_list_view": 1, "read_only": 1, "allow_in_quick_entry": 0}.items():
				if custom_field.get(key) != value:
					custom_field.set(key, value)
					changed = True
			if changed:
				custom_field.save(ignore_permissions=True)
			continue
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Sales Order",
			"fieldname": fieldname,
			"label": label,
			"fieldtype": "Data",
			"read_only": 1,
			"in_list_view": 1,
			"allow_in_quick_entry": 0,
			"insert_after": "customer_name" if fieldname == "sales_products" else "name",
		}).insert(ignore_permissions=True)
	frappe.db.updatedb("Sales Order")
	frappe.clear_cache(doctype="Sales Order")
