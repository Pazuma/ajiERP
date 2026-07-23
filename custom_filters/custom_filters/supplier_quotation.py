import frappe


def set_default_warehouse(doc, method=None):
	"""Fill empty item warehouses with the Buying Settings default.

	Only fills blank rows; values set by users or ERPNext's own logic
	(e.g. item default warehouse) are never overwritten.
	"""
	default = frappe.db.get_single_value(
		"Buying Settings", "custom_supplier_quotation_warehouse"
	)
	if not default:
		return
	for item in doc.items:
		if not item.warehouse:
			item.warehouse = default
