import frappe


def execute():
	"""Enable and show ERPNext accounting dimensions on all supported documents."""
	frappe.db.set_single_value("Accounts Settings", "enable_accounting_dimensions", 1)

	from erpnext.accounts.doctype.accounts_settings.accounts_settings import (
		toggle_accounting_dimension_sections,
	)

	toggle_accounting_dimension_sections(False)
	frappe.clear_cache()
