"""Add statutory inventory detail rows to the enterprise balance-sheet template."""


def execute():
	from china_finance.setup.templates import refresh_enterprise_v3_templates

	refresh_enterprise_v3_templates()
