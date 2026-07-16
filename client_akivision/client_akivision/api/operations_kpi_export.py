"""Excel export for the Operations KPI dashboard."""

import re
from io import BytesIO

import frappe
import xlsxwriter
from frappe import _
from frappe.desk.utils import provide_binary_file
from frappe.utils import now_datetime

from client_akivision.client_akivision.api.operations_kpi import get_kpi_dashboard_data


@frappe.whitelist()
def export_kpi_dashboard(filters=None):
	"""Export the dashboard using the same filters, permissions and calculations as the page."""
	data = get_kpi_dashboard_data(filters)
	content = build_kpi_workbook(data)
	filter_values = data["filters"]
	filename = _safe_filename(
		f"{_('Operations KPI Dashboard')}-{filter_values['company']}-{filter_values['from_date']}-{filter_values['to_date']}"
	)
	provide_binary_file(filename, "xlsx", content)


def build_kpi_workbook(data):
	output = BytesIO()
	workbook = xlsxwriter.Workbook(output, {"in_memory": True})
	formats = _make_formats(workbook, data)

	_write_overview_sheet(workbook, formats, data)
	_write_salesperson_sheet(workbook, formats, data)
	_write_receivable_sheet(workbook, formats, data)
	_write_operations_sheet(workbook, formats, data)
	_write_high_tech_sheet(workbook, formats, data)

	workbook.close()
	return output.getvalue()


def _make_formats(workbook, data):
	currency = frappe.get_cached_value("Company", data["filters"]["company"], "default_currency") or "CNY"
	return {
		"title": workbook.add_format(
			{"bold": True, "font_size": 18, "font_color": "#FFFFFF", "bg_color": "#2490EF", "align": "left", "valign": "vcenter"}
		),
		"filter_label": workbook.add_format({"bold": True, "font_color": "#475569", "bg_color": "#F1F5F9"}),
		"filter_value": workbook.add_format({"font_color": "#1E293B", "bg_color": "#F8FAFC"}),
		"section": workbook.add_format(
			{"bold": True, "font_size": 13, "font_color": "#1E3A5F", "bg_color": "#DBEAFE", "top": 1, "bottom": 1, "border_color": "#93C5FD"}
		),
		"header": workbook.add_format(
			{"bold": True, "font_color": "#FFFFFF", "bg_color": "#475569", "border": 1, "border_color": "#CBD5E1", "align": "center", "valign": "vcenter"}
		),
		"text": workbook.add_format({"border": 1, "border_color": "#E2E8F0", "valign": "vcenter"}),
		"number": workbook.add_format({"border": 1, "border_color": "#E2E8F0", "num_format": "0.00", "align": "right"}),
		"int": workbook.add_format({"border": 1, "border_color": "#E2E8F0", "num_format": "0", "align": "right"}),
		"currency": workbook.add_format(
			{"border": 1, "border_color": "#E2E8F0", "num_format": f'"{currency}" #,##0.00', "align": "right"}
		),
		"percent": workbook.add_format({"border": 1, "border_color": "#E2E8F0", "num_format": "0.0%", "align": "right"}),
		"date": workbook.add_format({"border": 1, "border_color": "#E2E8F0", "num_format": "yyyy-mm-dd", "align": "center"}),
		"empty": workbook.add_format({"italic": True, "font_color": "#94A3B8", "align": "center", "border": 1, "border_color": "#E2E8F0"}),
	}


def _setup_sheet(workbook, formats, data, name, column_widths):
	worksheet = workbook.add_worksheet(_sheet_name(name))
	worksheet.hide_gridlines(2)
	worksheet.freeze_panes(5, 0)
	worksheet.set_row(0, 30)
	last_column = max(7, len(column_widths) - 1)
	worksheet.merge_range(0, 0, 0, last_column, _("Operations KPI Dashboard"), formats["title"])
	filters = data["filters"]
	filter_items = [
		(_("Company"), filters["company"]),
		(_("From Date"), filters["from_date"]),
		(_("To Date"), filters["to_date"]),
		(_("Generated At"), str(now_datetime())),
	]
	for column, (label, value) in enumerate(filter_items):
		worksheet.write(2, column * 2, label, formats["filter_label"])
		worksheet.write(2, column * 2 + 1, value, formats["filter_value"])
	for column, width in enumerate(column_widths):
		worksheet.set_column(column, column, width)
	if len(column_widths) <= last_column:
		worksheet.set_column(len(column_widths), last_column, 14)
	return worksheet, 4


def _write_overview_sheet(workbook, formats, data):
	worksheet, row = _setup_sheet(workbook, formats, data, _("KPI Overview"), [30, 18, 18, 16, 16])
	sections = [
		(_("Sales Overview"), data.get("sales"), [
			("total_orders", _("Total Orders")),
			("total_sales_amount", _("Total Sales Amount")),
			("high_tech_revenue", _("High-tech Revenue Amount")),
			("high_tech_ratio", _("High-tech Revenue Ratio")),
		]),
		(_("Order Fulfillment"), data.get("delivery"), [
			("completed_orders", _("Completed Orders")),
			("pending_orders", _("Pending Orders")),
			("delivered_orders", _("Delivered Orders")),
			("delivering_orders", _("Delivering Orders")),
			("undelivered_orders", _("Undelivered Orders")),
		]),
		(_("Collection and Receivables"), data.get("receivable"), [
			("received_amount", _("Collection Amount")),
			("receivable_amount", _("Receivable Amount")),
			("settled_documents", _("Settled Documents")),
			("unsettled_documents", _("Unsettled Documents")),
			("overdue_over_90", _("Over 90 Days Overdue")),
			("monthly_collection_completion", _("Monthly Collection Target Completion")),
		]),
		(_("Year-over-year Indicators"), data.get("year_over_year"), [
			("prior_sales_amount", _("Prior-period Sales Amount")),
			("sales_growth_rate", _("Sales Growth Rate")),
			("receivable_growth_rate", _("Receivable Growth Rate")),
		]),
		(_("Reconciliation Warning"), data.get("reconciliation"), [
			("unfinished_orders", _("Unfinished Orders")),
			("status_mismatch_count", _("Status Mismatch Count")),
		]),
		(_("Receivable Core Control Indicators"), data.get("receivable"), [
			("total_receivable_balance", _("Receivable Balance")),
			("aging_0_30", _("Due Within 30 Days")),
			("aging_31_90", _("31-90 Days Overdue")),
			("aging_over_90", _("Over 90 Days Overdue")),
		]),
		(_("Production and Purchasing Operations"), data.get("operations"), [
			("production_completion_rate", _("Production Completion Rate")),
			("purchase_on_time_rate", _("Purchase On-time Rate")),
			("realtime_inventory_amount", _("Realtime Inventory Amount")),
			("safety_stock_warning_count", _("Safety Stock Warning Count")),
			("purchase_in_transit_amount", _("Purchase In-transit Amount")),
			("material_over_consumption_rate", _("Material Over-consumption Rate")),
		]),
		(_("High-tech Compliance"), data.get("high_tech"), [
			("high_tech_revenue", _("High-tech Revenue Amount")),
			("total_revenue", _("Total Revenue")),
			("high_tech_ratio", _("High-tech Revenue Ratio")),
			("rd_project_count", _("RD Project Count")),
			("rd_expense_amount", _("RD Expense Amount")),
			("rd_expense_ratio", _("RD Expense Ratio")),
		]),
	]
	for section_title, source, metrics in sections:
		row = _write_metric_section(worksheet, formats, row, section_title, source or {}, metrics)


def _write_metric_section(worksheet, formats, row, title, source, metrics):
	worksheet.merge_range(row, 0, row, 4, title, formats["section"])
	row += 1
	for column, label in enumerate([_("Metric"), _("Value"), _("Target Value"), _("Achievement Rate"), _("Warning Status")]):
		worksheet.write(row, column, label, formats["header"])
	row += 1
	for key, label in metrics:
		metric = source.get(key) or {}
		worksheet.write(row, 0, label, formats["text"])
		_write_metric_value(worksheet, row, 1, metric.get("value"), metric.get("datatype"), formats)
		_write_metric_value(worksheet, row, 2, metric.get("target"), metric.get("datatype"), formats)
		_write_value(worksheet, row, 3, metric.get("achievement"), "percent", formats)
		status = metric.get("status")
		worksheet.write(row, 4, "" if status == "未设置" else (status or ""), formats["text"])
		row += 1
	return row + 1


def _write_salesperson_sheet(workbook, formats, data):
	worksheet, row = _setup_sheet(workbook, formats, data, _("Salesperson Performance"), [22, 14, 18, 18, 18, 14, 14])
	columns = [
		(_("Sales Person"), "sales_person", "text"),
		(_("Delivery Count"), "delivery_count", "int"),
		(_("Delivery Amount"), "delivery_amount", "currency"),
		(_("Personal Collection"), "personal_received", "currency"),
		(_("Personal Receivable"), "personal_receivable", "currency"),
		(_("Delivery Rate"), "delivery_rate", "percent"),
		(_("Collection Rate"), "collection_rate", "percent"),
	]
	_write_table(worksheet, formats, row, _("Salesperson Performance"), data.get("salesperson") or [], columns)


def _write_receivable_sheet(workbook, formats, data):
	worksheet, row = _setup_sheet(workbook, formats, data, _("Receivable Aging"), [24, 20, 18, 18])
	row = _write_table(
		worksheet,
		formats,
		row,
		_("Receivable Aging Distribution"),
		(data.get("aging") or {}).get("distribution") or [],
		[(_("Aging Period"), "label", "text"), (_("Amount"), "amount", "currency"), (_("Ratio"), "ratio", "percent")],
	)
	_write_table(
		worksheet,
		formats,
		row,
		_("Top 10 Overdue Customers"),
		(data.get("aging") or {}).get("top_customers") or [],
		[(_("Customer"), "customer_name", "text"), (_("Overdue Amount"), "overdue_amount", "currency"), (_("Overdue Days"), "overdue_days", "int"), (_("Risk Level"), "risk_level", "text")],
	)


def _write_operations_sheet(workbook, formats, data):
	worksheet, row = _setup_sheet(workbook, formats, data, _("Production and Purchasing Operations"), [24, 18, 18, 18])
	row = _write_table(
		worksheet,
		formats,
		row,
		_("Monthly Production Completion Trend"),
		data.get("production_trend") or [],
		[(_("Period"), "period", "text"), (_("Planned Quantity"), "planned_qty", "number"), (_("Actual Quantity"), "actual_qty", "number"), (_("Completion Rate"), "completion_rate", "percent")],
	)
	_write_table(
		worksheet,
		formats,
		row,
		_("Top 10 Delayed Suppliers"),
		data.get("delayed_suppliers") or [],
		[(_("Supplier"), "supplier_name", "text"), (_("Delayed Orders"), "delayed_order_count", "int"), (_("Average Delay Days"), "average_delay_days", "number"), (_("Risk Level"), "risk_level", "text")],
	)


def _write_high_tech_sheet(workbook, formats, data):
	worksheet, row = _setup_sheet(workbook, formats, data, _("High-tech Compliance"), [26, 22, 20])
	row = _write_table(
		worksheet,
		formats,
		row,
		_("3-Year High-tech Trend"),
		data.get("high_tech_trend") or [],
		[(_("Year"), "year", "int"), (_("High-tech Revenue Amount"), "high_tech_revenue", "currency"), (_("Total Revenue"), "total_revenue", "currency")],
	)
	_write_table(
		worksheet,
		formats,
		row,
		_("Top 10 RD Projects"),
		data.get("high_tech_projects") or [],
		[(_("Project"), "project_name", "text"), (_("High-tech Revenue Amount"), "high_tech_revenue", "currency")],
	)


def _write_table(worksheet, formats, row, title, rows, columns):
	last_column = max(0, len(columns) - 1)
	worksheet.merge_range(row, 0, row, last_column, title, formats["section"])
	row += 1
	for column, (label, _fieldname, _fieldtype) in enumerate(columns):
		worksheet.write(row, column, label, formats["header"])
	row += 1
	if not rows:
		worksheet.merge_range(row, 0, row, last_column, _("No data matching the current filters."), formats["empty"])
		return row + 2
	for item in rows:
		for column, (_label, fieldname, fieldtype) in enumerate(columns):
			_write_value(worksheet, row, column, item.get(fieldname), fieldtype, formats)
		row += 1
	return row + 1


def _write_metric_value(worksheet, row, column, value, datatype, formats):
	fieldtype = {"Currency": "currency", "Percent": "percent", "Int": "int"}.get(datatype, "number")
	_write_value(worksheet, row, column, value, fieldtype, formats)


def _write_value(worksheet, row, column, value, fieldtype, formats):
	if value is None or value == "":
		worksheet.write_blank(row, column, None, formats["text"])
	elif fieldtype in {"currency", "percent", "int", "number"}:
		worksheet.write_number(row, column, float(value), formats[fieldtype])
	else:
		worksheet.write(row, column, str(value), formats["text"])


def _sheet_name(name):
	return re.sub(r"[\[\]:*?/\\]", "-", str(name))[:31]


def _safe_filename(filename):
	return re.sub(r"[\\/:*?\"<>|]", "-", filename).strip(" .")
