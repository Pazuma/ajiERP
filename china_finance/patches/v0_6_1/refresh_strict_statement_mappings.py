import frappe

from china_finance.setup.templates import sync_automatic_cash_flow_mappings, sync_unreviewed_automatic_mappings


def execute():
	for settings in frappe.get_all(
		"China Finance Settings", filters={"enabled": 1, "accounting_standard": "企业会计准则"},
		fields=["company", "accounting_standard"],
	):
		sync_unreviewed_automatic_mappings(settings.company, settings.accounting_standard)
		sync_automatic_cash_flow_mappings(settings.company, settings.accounting_standard)
