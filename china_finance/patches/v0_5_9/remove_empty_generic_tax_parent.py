import frappe

from china_finance.setup.china_coa_profile import normalize_generic_vat_templates


def execute():
	for company in frappe.get_all(
		"Company", filters={"chart_of_accounts": "中国企业会计准则－一般纳税人制造业（1.0）"}, pluck="name"
	):
		normalize_generic_vat_templates(company)
