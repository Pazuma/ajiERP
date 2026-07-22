import frappe
from frappe.modules.import_file import import_file_by_path


def execute():
	"""Restore ERPNext metadata after removing the experimental sidebar override."""
	paths = (
		frappe.get_app_path("erpnext", "workspace_sidebar", "financial_reports.json"),
		frappe.get_app_path(
			"erpnext", "accounts", "workspace", "financial_reports", "financial_reports.json"
		),
	)
	for path in paths:
		import_file_by_path(path, force=True)
