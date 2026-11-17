from china_finance.services.sales_commission_reports import execute as run_report


def execute(filters=None):
	return run_report(filters, personal=False)

