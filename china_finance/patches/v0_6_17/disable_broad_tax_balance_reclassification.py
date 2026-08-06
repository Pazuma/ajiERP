import frappe


def execute():
	"""Disable the broad tax rule; tax presentation needs tax-account context."""
	frappe.db.set_value(
		"China Financial Statement Reclassification Rule",
		{
			"source_row_code": "TAXES_PAYABLE",
			"source_direction": "Credit Positive",
			"target_row_code": "OTHER_CURRENT_ASSETS",
			"enabled": 1,
		},
		"enabled",
		0,
		update_modified=False,
	)
