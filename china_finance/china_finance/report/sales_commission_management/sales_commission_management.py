from china_finance.services.sales_commission_permissions import can_manage, can_finance
from china_finance.services.sales_commission_reports import execute as run_report


def execute(filters=None):
	# Client filters never decide whether colleagues' rows are visible.
	return run_report(filters, personal=not (can_manage() or can_finance()))
