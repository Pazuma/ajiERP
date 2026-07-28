"""Make the small-enterprise inventory total include its statutory detail rows."""


def execute():
	from china_finance.setup.templates import refresh_small_enterprise_v3_templates

	refresh_small_enterprise_v3_templates()
