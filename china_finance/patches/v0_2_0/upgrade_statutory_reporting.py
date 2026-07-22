import frappe


def execute():
	from china_finance.setup.templates import ensure_company_mappings, seed_statement_templates

	seed_statement_templates()
	if frappe.db.exists("DocType", "China Finance Settings"):
		frappe.db.sql(
			"""UPDATE `tabChina Finance Settings`
			SET reconciliation_tolerance=0.01
			WHERE reconciliation_tolerance IS NULL OR reconciliation_tolerance<=0"""
		)
		for fieldname in (
			"require_customer_reconciliation", "require_supplier_reconciliation", "require_bank_reconciliation"
		):
			if frappe.db.has_column("China Finance Settings", fieldname):
				frappe.db.sql(
					f"UPDATE `tabChina Finance Settings` SET `{fieldname}`=1 WHERE `{fieldname}` IS NULL"
				)
	ensure_company_mappings()

