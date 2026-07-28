"""Refresh unreviewed small-enterprise inventory detail mappings."""

import frappe


def execute():
	from china_finance.setup.templates import ensure_company_mappings, sync_unreviewed_automatic_mappings

	for settings in frappe.get_all(
		"China Finance Settings",
		filters={"enabled": 1, "accounting_standard": "小企业会计准则"},
		fields=["company"],
	):
		sync_unreviewed_automatic_mappings(settings.company, "小企业会计准则")
	ensure_company_mappings()
