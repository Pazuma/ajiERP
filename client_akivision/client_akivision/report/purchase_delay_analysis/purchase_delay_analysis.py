from frappe import _
from frappe.utils import flt

from client_akivision.client_akivision.api.operations_kpi import get_purchase_delay_rows, normalise_filters


def execute(filters=None):
	filters = normalise_filters(filters)
	data = get_purchase_delay_rows(filters)
	if filters.get("supplier"):
		data = [row for row in data if row.supplier == filters.supplier]
	return get_columns(), data, None, None, get_summary(data), 1


def get_columns():
	return [
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 140},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": _("Purchase Orders"), "fieldname": "order_count", "fieldtype": "Int", "width": 105},
		{"label": _("Evaluated Orders"), "fieldname": "evaluated_order_count", "fieldtype": "Int", "width": 110},
		{"label": _("Pending Evaluation Orders"), "fieldname": "pending_order_count", "fieldtype": "Int", "width": 120},
		{"label": _("On-time Orders"), "fieldname": "on_time_order_count", "fieldtype": "Int", "width": 115},
		{"label": _("Delayed Orders"), "fieldname": "delayed_order_count", "fieldtype": "Int", "width": 110},
		{"label": _("Open Overdue Orders"), "fieldname": "open_overdue_order_count", "fieldtype": "Int", "width": 115},
		{"label": _("Max Open Overdue (Days)"), "fieldname": "max_open_overdue_days", "fieldtype": "Int", "width": 125},
		{"label": _("Average Delay Days"), "fieldname": "average_delay_days", "fieldtype": "Float", "width": 130},
		{"label": _("Average Lead Time (Days)"), "fieldname": "average_lead_time_days", "fieldtype": "Float", "width": 130},
		{"label": _("Risk Level"), "fieldname": "risk_level", "fieldtype": "Data", "width": 100},
	]


def get_summary(data):
	delayed = sum(flt(row.delayed_order_count) for row in data)
	orders = sum(flt(row.order_count) for row in data)
	evaluated = sum(flt(row.evaluated_order_count) for row in data)
	on_time = sum(flt(row.on_time_order_count) for row in data)
	pending = sum(flt(row.pending_order_count) for row in data)
	return [
		{"label": _("采购订单数"), "value": orders, "datatype": "Int", "indicator": "Blue"},
		{"label": _("已评估订单数"), "value": evaluated, "datatype": "Int", "indicator": "Blue"},
		{"label": _("待评估订单数"), "value": pending, "datatype": "Int", "indicator": "Orange"},
		{"label": _("延迟订单数"), "value": delayed, "datatype": "Int", "indicator": "Red"},
		{"label": _("采购到货及时率"), "value": on_time / evaluated * 100 if evaluated else 0, "datatype": "Percent", "indicator": "Green"},
	]
