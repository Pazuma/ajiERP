"""Make the statutory small-enterprise balance-sheet hierarchy explicit."""


def execute():
	from china_finance.setup.templates import refresh_small_enterprise_v3_templates

	refresh_small_enterprise_v3_templates()
