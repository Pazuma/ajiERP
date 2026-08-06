import frappe


def execute():
	"""Enable the configured presentation rule for debit tax balances."""
	frappe.db.set_value(
		"China Financial Statement Reclassification Rule",
		{
			"source_row_code": "TAXES_PAYABLE",
			"source_direction": "Credit Positive",
			"target_row_code": "OTHER_CURRENT_ASSETS",
		},
		"enabled",
		1,
		update_modified=False,
	)
