"""Hide legacy free-text employee fields on Timesheet."""

import frappe


LEGACY_FIELDS = ("custom_excel_employee_name", "custom_excel_department")


def hide_legacy_timesheet_fields():
	"""Keep imported legacy data while removing duplicate inputs from the form."""
	changed = False
	for fieldname in LEGACY_FIELDS:
		name = frappe.db.get_value("Custom Field", {"dt": "Timesheet", "fieldname": fieldname}, "name")
		if name and not frappe.db.get_value("Custom Field", name, "hidden"):
			frappe.db.set_value("Custom Field", name, "hidden", 1, update_modified=False)
			changed = True

	if changed:
		frappe.clear_cache(doctype="Timesheet")
