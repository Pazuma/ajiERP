from frappe import _


def get_work_order_dashboard(data):
	"""Show upstream references and production documents on Work Order connections."""
	data.internal_links.update(
		{
			"Sales Order": "sales_order",
			"Project": "project",
			"Material Request": "material_request",
			"Production Plan": "production_plan",
			"BOM": "bom_no",
		}
	)
	data.transactions = [
		{"label": _("Reference"), "items": ["Sales Order", "Project", "Material Request", "Production Plan", "BOM"]},
		{"label": _("Transactions"), "items": ["Stock Entry", "Job Card", "Pick List"]},
		{"label": _("Traceability"), "items": ["Serial No", "Batch"]},
		{"label": _("Stock Reservation"), "items": ["Stock Reservation Entry"]},
	]
	return data
