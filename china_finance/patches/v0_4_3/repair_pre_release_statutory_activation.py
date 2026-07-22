import frappe
from frappe.utils import getdate


FORMAL_V3_START = getdate("2026-01-01")


def execute():
	"""Repair the activation date written by the pre-release v0_4_0 patch only."""
	for settings in frappe.get_all(
		"China Finance Settings",
		filters={"enabled": 1, "accounting_standard": "企业会计准则"},
		fields=["name", "company", "activation_date", "statutory_reporting_activation_date"],
	):
		if (
			not settings.statutory_reporting_activation_date
			or getdate(settings.statutory_reporting_activation_date) != getdate(settings.activation_date)
			or getdate(settings.statutory_reporting_activation_date) <= FORMAL_V3_START
		):
			continue
		templates = frappe.get_all(
			"China Financial Statement Template",
			filters={"accounting_standard": "企业会计准则", "version": "3.0"},
			pluck="name",
		)
		if any(frappe.db.exists("China Report Snapshot", {"template": template}) for template in templates):
			continue
		frappe.db.set_value(
			"China Finance Settings", settings.name,
			"statutory_reporting_activation_date", FORMAL_V3_START,
			update_modified=False,
		)
		for mapping_name in frappe.get_all(
			"China Financial Statement Mapping",
			filters={
				"company": settings.company, "template": ["in", templates],
				"mapping_source": "Automatic", "reviewed": 0,
			},
			pluck="name",
		):
			mapping = frappe.get_doc("China Financial Statement Mapping", mapping_name)
			mapping.effective_from = FORMAL_V3_START
			mapping.flags.ignore_permissions = True
			mapping.save()
