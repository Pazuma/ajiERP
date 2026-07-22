import frappe

from china_finance.china_finance.report.china_purchase_reconciliation.china_purchase_reconciliation import (
	get_purchase_order_columns,
)
from china_finance.services.purchase_reconciliation import get_purchase_order_reconciliation_rows

def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_purchase_order_reconciliation_rows(
		filters.company, filters.from_date, filters.to_date, filters.supplier, filters.get("purchase_order")
	)
	if filters.get("exception_only"):
		data = [row for row in data if row.reconciliation_status == "Blocked"]
	return get_purchase_order_columns(), data
