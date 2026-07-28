"""Create the standard China Financial Statements report print format."""


def execute():
	from china_finance.setup.install import sync_china_financial_statement_print_format

	sync_china_financial_statement_print_format()
