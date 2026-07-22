import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from china_finance.services.financial_statement import (
	build_statement,
	get_comparison_period,
	get_fiscal_year_start,
	get_template,
)


def _apply_default_period(filters):
	"""Resolve the report period before the browser-side filter script is ready."""
	to_date = getdate(filters.to_date or nowdate())
	filters.to_date = to_date
	filters.from_date = getdate(filters.from_date or get_fiscal_year_start(filters.company, to_date))


def execute(filters=None):
	filters = frappe._dict(filters or {})
	_apply_default_period(filters)
	result = build_statement(
		filters.company,
		filters.statement_type,
		filters.from_date,
		filters.to_date,
		filters.finance_book,
		filters.cost_center,
		filters.project,
	)
	comparison_from = filters.comparison_from_date
	comparison_to = filters.comparison_to_date
	if not comparison_to:
		comparison_from, comparison_to = get_comparison_period(
			filters.company, filters.statement_type, filters.from_date, filters.to_date
		)
	if comparison_to and get_template(
		filters.company, filters.statement_type, comparison_to, required=False
	):
		comparison = build_statement(
			filters.company,
			filters.statement_type,
			comparison_from,
			comparison_to,
			filters.finance_book,
			filters.cost_center,
			filters.project,
		)
		comparison_values = {row["row_code"]: row["amount"] for row in comparison["rows"]}
		for row in result["rows"]:
			row["comparison_amount"] = comparison_values.get(row["row_code"], 0)
		result["warnings"].extend(comparison["warnings"])
	elif comparison_to:
		result["warnings"].append(
			_("比较期 {0} 未配置适用报表模板，当前仅显示本期草表").format(comparison_to)
		)
		comparison_to = None
	warnings = list(dict.fromkeys(result["warnings"]))
	message_parts = [_('编制状态：草表。正式法定财务报表须从已通过检查的结账运行单生成。')]
	message_parts.extend(warnings)
	message = "<br>".join(message_parts)
	if filters.statement_type == "Balance Sheet":
		return (
			get_balance_sheet_columns(bool(comparison_to)),
			build_balance_sheet_rows(result["rows"]),
			message,
			get_balance_sheet_chart(result["rows"], filters.company, filters),
			get_balance_sheet_summary(result["rows"], filters.company),
		)
	if filters.statement_type == "Profit and Loss":
		return (
			get_columns(),
			result["rows"],
			message,
			get_profit_and_loss_chart(result["rows"], filters.company, filters),
			get_profit_and_loss_summary(result["rows"], filters.company),
		)
	if filters.statement_type == "Cash Flow":
		return (
			get_columns(),
			result["rows"],
			message,
			get_cash_flow_chart(result["rows"], filters.company, filters),
			get_cash_flow_summary(result["rows"], filters.company),
		)
	if filters.statement_type == "Changes in Equity" and result.get("equity_matrix"):
		return get_equity_columns(result["equity_matrix"]), result["equity_matrix"]["rows"], message
	return get_columns(), result["rows"], message


def get_columns():
	return [
		{"label": _("项目"), "fieldname": "label", "fieldtype": "Data", "width": 420},
		{"label": _("期初金额"), "fieldname": "opening_amount", "fieldtype": "Currency", "width": 160},
		{"label": _("本期金额/期末余额"), "fieldname": "amount", "fieldtype": "Currency", "width": 180},
		{"label": _("本年累计"), "fieldname": "year_to_date_amount", "fieldtype": "Currency", "width": 160},
		{"label": _("比较期金额"), "fieldname": "comparison_amount", "fieldtype": "Currency", "width": 180},
	]


def get_equity_columns(matrix):
	columns = [{"label": _("项目"), "fieldname": "label", "fieldtype": "Data", "width": 320}]
	columns.extend(
		{"label": _(component["label"]), "fieldname": component["fieldname"], "fieldtype": "Currency", "width": 150}
		for component in matrix["components"]
	)
	columns.append({"label": _("所有者权益合计"), "fieldname": "total", "fieldtype": "Currency", "width": 170})
	return columns


def get_balance_sheet_columns(include_comparison=False):
	columns = [
		{"label": _("资产"), "fieldname": "asset_label", "fieldtype": "Data", "width": 280},
		{"label": _("期初余额"), "fieldname": "asset_opening_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("期末余额"), "fieldname": "asset_amount", "fieldtype": "Currency", "width": 150},
	]
	if include_comparison:
		columns.append({"label": _("比较期余额"), "fieldname": "asset_comparison_amount", "fieldtype": "Currency", "width": 150})
	columns.extend([
		{"label": _("负债和所有者权益"), "fieldname": "liability_equity_label", "fieldtype": "Data", "width": 280},
		{"label": _("期初余额"), "fieldname": "liability_equity_opening_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("期末余额"), "fieldname": "liability_equity_amount", "fieldtype": "Currency", "width": 150},
	])
	if include_comparison:
		columns.append({"label": _("比较期余额"), "fieldname": "liability_equity_comparison_amount", "fieldtype": "Currency", "width": 150})
	return columns


def build_balance_sheet_rows(rows):
	"""Pair statutory assets with liabilities and equity for a two-sided balance sheet."""
	asset_end = next((index for index, row in enumerate(rows) if row["row_code"] == "TOTAL_ASSETS"), -1)
	if asset_end < 0:
		return rows
	asset_rows = rows[: asset_end + 1]
	liability_equity_rows = rows[asset_end + 1 :]
	paired_rows = []
	for index in range(max(len(asset_rows), len(liability_equity_rows))):
		asset = asset_rows[index] if index < len(asset_rows) else {}
		liability_equity = liability_equity_rows[index] if index < len(liability_equity_rows) else {}
		paired_rows.append({
			"indent": max(asset.get("indent", 0), liability_equity.get("indent", 0)),
			"asset_label": asset.get("label"),
			"asset_row_type": asset.get("row_type"),
			"asset_opening_amount": asset.get("opening_amount"),
			"asset_amount": asset.get("amount"),
			"asset_comparison_amount": asset.get("comparison_amount"),
			"asset_indent": asset.get("indent", 0),
			"asset_bold": asset.get("bold", 0),
			"liability_equity_label": liability_equity.get("label"),
			"liability_equity_row_type": liability_equity.get("row_type"),
			"liability_equity_opening_amount": liability_equity.get("opening_amount"),
			"liability_equity_amount": liability_equity.get("amount"),
			"liability_equity_comparison_amount": liability_equity.get("comparison_amount"),
			"liability_equity_indent": liability_equity.get("indent", 0),
			"liability_equity_bold": liability_equity.get("bold", 0),
		})
	return paired_rows


def get_balance_sheet_chart(rows, company, filters):
	amounts = {row["row_code"]: flt(row.get("amount")) for row in rows}
	period_label = filters.get("accounting_period") or filters.get("to_date")
	return {
		"data": {
			"labels": [period_label],
			"datasets": [
				{"name": _("资产"), "values": [amounts.get("TOTAL_ASSETS", 0)]},
				# The chart uses the zero axis to distinguish the two sides of the accounting equation.
				{"name": _("负债"), "values": [-amounts.get("TOTAL_LIABILITIES", 0)]},
				{"name": _("所有者权益"), "values": [-amounts.get("OWNERS_EQUITY", 0)]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"colors": ["#2563eb", "#f59e0b", "#16a34a"],
	}


def get_balance_sheet_summary(rows, company):
	amounts = {row["row_code"]: flt(row.get("amount")) for row in rows}
	total_assets = amounts.get("TOTAL_ASSETS", 0)
	total_liabilities = amounts.get("TOTAL_LIABILITIES", 0)
	total_equity = amounts.get("OWNERS_EQUITY", 0)
	balance_difference = flt(total_assets - total_liabilities - total_equity, 2)
	currency = frappe.get_cached_value("Company", company, "default_currency")
	return [
		{"value": total_assets, "label": _("资产总计"), "datatype": "Currency", "currency": currency},
		{"value": total_liabilities, "label": _("负债合计"), "datatype": "Currency", "currency": currency},
		{"value": total_equity, "label": _("所有者权益合计"), "datatype": "Currency", "currency": currency},
		{
			"value": balance_difference,
			"label": _("平衡差额（资产 - 负债 - 所有者权益）"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if not balance_difference else "Red",
		},
	]


def get_profit_and_loss_metrics(rows):
	"""Calculate year-to-date highlights using stable statutory report row codes."""
	amounts = {row["row_code"]: flt(row.get("year_to_date_amount")) for row in rows}
	total_expenses = sum(
		amounts.get(code, 0)
		for code in (
			"OPERATING_COST",
			"TAX_SURCHARGES",
			"SELLING_EXPENSES",
			"ADMIN_EXPENSES",
			"RD_EXPENSES",
			"FINANCE_EXPENSES",
			"NONOPERATING_EXPENSE",
			"INCOME_TAX",
		)
	)
	return {
		"income": amounts.get("OPERATING_REVENUE", 0),
		"expenses": total_expenses,
		"profit": amounts.get("NET_PROFIT", 0),
	}


def get_profit_and_loss_chart(rows, company, filters):
	metrics = get_profit_and_loss_metrics(rows)
	period_label = filters.get("accounting_period") or filters.get("to_date")
	return {
		"data": {
			"labels": [period_label],
			"datasets": [
				# Present the operating bridge consistently: income increases profit,
				# expenses reduce it, and profit keeps its actual accounting sign.
				{"name": _("收入"), "values": [metrics["income"]]},
				{"name": _("费用"), "values": [-metrics["expenses"]]},
				{"name": _("净利润"), "values": [metrics["profit"]]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"colors": ["#ec6d9d", "#3187d4", "#45b978"],
	}


def get_profit_and_loss_summary(rows, company):
	metrics = get_profit_and_loss_metrics(rows)
	currency = frappe.get_cached_value("Company", company, "default_currency")
	return [
		{"value": metrics["income"], "label": _("本年收入"), "datatype": "Currency", "currency": currency},
		{"value": metrics["expenses"], "label": _("本年费用"), "datatype": "Currency", "currency": currency},
		{
			"value": metrics["profit"],
			"label": _("本年利润"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if metrics["profit"] >= 0 else "Red",
		},
	]


def get_cash_flow_metrics(rows):
	"""Calculate cash-flow highlights from the statutory cash-flow rows."""
	amounts = {row["row_code"]: flt(row.get("year_to_date_amount")) for row in rows}
	return {
		"operating": amounts.get("OPERATING_CASH_FLOW", 0),
		"investing": amounts.get("INVESTING_CASH_FLOW", 0),
		"financing": amounts.get("FINANCING_CASH_FLOW", 0),
		"net_increase": amounts.get("NET_CASH_INCREASE", 0),
	}


def get_cash_flow_chart(rows, company, filters):
	metrics = get_cash_flow_metrics(rows)
	period_label = filters.get("accounting_period") or filters.get("to_date")
	return {
		"data": {
			"labels": [period_label],
			"datasets": [
				{"name": _("经营活动"), "values": [metrics["operating"]]},
				{"name": _("投资活动"), "values": [metrics["investing"]]},
				{"name": _("筹资活动"), "values": [metrics["financing"]]},
				{"name": _("现金净增加额"), "values": [metrics["net_increase"]]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"colors": ["#16a34a", "#f59e0b", "#2563eb", "#e76f51"],
	}


def get_cash_flow_summary(rows, company):
	metrics = get_cash_flow_metrics(rows)
	currency = frappe.get_cached_value("Company", company, "default_currency")
	return [
		{
			"value": metrics["operating"],
			"label": _("本年经营活动现金流净额"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if metrics["operating"] >= 0 else "Red",
		},
		{
			"value": metrics["investing"],
			"label": _("本年投资活动现金流净额"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": metrics["financing"],
			"label": _("本年筹资活动现金流净额"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": metrics["net_increase"],
			"label": _("本年现金净增加额"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if metrics["net_increase"] >= 0 else "Red",
		},
	]
