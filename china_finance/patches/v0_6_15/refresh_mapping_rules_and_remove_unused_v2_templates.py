"""Refresh only safe automatic suggestions and retire truly unused 2.0 templates."""

import frappe

from china_finance.setup.templates import (
	ensure_company_mappings,
	refresh_small_enterprise_v3_templates,
	sync_unreviewed_automatic_mappings,
)


def execute():
	refresh_small_enterprise_v3_templates()
	ensure_company_mappings()
	for settings in frappe.get_all(
		"China Finance Settings", filters={"enabled": 1}, fields=["company", "accounting_standard"]
	):
		sync_unreviewed_automatic_mappings(settings.company, settings.accounting_standard)
	_remove_unused_v2_templates()


def _remove_unused_v2_templates():
	"""Never delete a template that still carries mapping or snapshot evidence."""
	for template in frappe.get_all(
		"China Financial Statement Template",
		filters={"version": "2.0"},
		fields=["name", "accounting_standard", "statement_type"],
	):
		if frappe.db.exists("China Financial Statement Mapping", {"template": template.name}):
			frappe.logger("china_finance").warning(
				"保留 2.0 报表模板 %s：仍存在科目映射引用。", template.name
			)
			continue
		if frappe.db.exists("China Report Snapshot", {"template": template.name}):
			frappe.logger("china_finance").warning(
				"保留 2.0 报表模板 %s：仍存在报表快照引用。", template.name
			)
			continue
		frappe.delete_doc("China Financial Statement Template", template.name, ignore_permissions=True, force=1)
