from china_finance.setup.install import sync_china_financial_statement_report_filters


def execute():
	"""Add the native Trial Balance option without removing custom filters."""
	sync_china_financial_statement_report_filters()
