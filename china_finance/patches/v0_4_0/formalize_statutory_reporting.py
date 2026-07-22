import frappe


def execute():
	from china_finance.setup.templates import ensure_company_mappings, seed_cash_equivalent_scope, seed_statement_templates

	seed_statement_templates()
	seed_cash_equivalent_scope()
	for settings in frappe.get_all(
		"China Finance Settings", filters={"enabled": 1, "accounting_standard": "企业会计准则"},
		fields=["name", "activation_date", "statutory_reporting_activation_date"],
	):
		if not settings.statutory_reporting_activation_date:
			frappe.db.set_value(
				"China Finance Settings", settings.name, "statutory_reporting_activation_date",
				frappe.utils.getdate("2026-01-01"),
				update_modified=False,
			)
	ensure_company_mappings()
