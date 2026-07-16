import frappe
from frappe import _
from frappe.utils import flt

from client_akivision.client_akivision.api.operations_kpi import get_receivable_aging_rows, normalise_filters


def execute(filters=None):
	filters = normalise_filters(filters)
	data = get_receivable_aging_rows(filters)
	if filters.get("customer"):
		data = [row for row in data if row.customer == filters.customer]
	return get_columns(), data, None, None, get_summary(data)


def get_columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 95},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 135},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Invoice Amount"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 118},
		{"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Receivable Days"), "fieldname": "receivable_days", "fieldtype": "Int", "width": 88},
		{"label": _("Aging Period"), "fieldname": "aging_label", "fieldtype": "Data", "width": 115},
		{"label": _("Risk Level"), "fieldname": "risk_level", "fieldtype": "Data", "width": 96},
		{"label": _("Receipt Status"), "fieldname": "status", "fieldtype": "Data", "width": 92},
	]


def get_summary(data):
	open_rows = [row for row in data if flt(row.outstanding_amount)]
	return [
		{"label": _("应收总余额"), "value": sum(flt(row.outstanding_amount) for row in open_rows), "datatype": "Currency", "indicator": "Orange"},
		{"label": _("未结清单据数"), "value": len(open_rows), "datatype": "Int", "indicator": "Orange"},
		{"label": _("超90天逾期应收金额"), "value": sum(flt(row.outstanding_amount) for row in open_rows if row.receivable_days > 90), "datatype": "Currency", "indicator": "Red"},
	]
