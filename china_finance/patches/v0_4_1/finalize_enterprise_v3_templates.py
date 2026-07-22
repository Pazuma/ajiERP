def execute():
	from china_finance.setup.templates import ensure_company_mappings, refresh_enterprise_v3_templates

	refresh_enterprise_v3_templates()
	ensure_company_mappings()
