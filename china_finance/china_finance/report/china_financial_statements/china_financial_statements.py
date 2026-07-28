import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate
from frappe.utils.file_manager import save_file
from frappe.utils.pdf import get_pdf

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
	if filters.statement_type == "Trial Balance":
		return execute_native_trial_balance(filters)
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
			restate_prior_period=True,
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
			get_cash_flow_summary(result["rows"], filters.company, filters),
		)
	if filters.statement_type == "Changes in Equity" and result.get("equity_matrix"):
		return get_equity_columns(result["equity_matrix"]), result["equity_matrix"]["rows"], message
	return get_columns(), result["rows"], message


def execute_native_trial_balance(filters):
	"""Render ERPNext's native Trial Balance inside this report page."""
	from erpnext.accounts.report.trial_balance.trial_balance import execute as execute_trial_balance

	native_filters = frappe._dict({
		"company": filters.company,
		"fiscal_year": filters.fiscal_year,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
		"finance_book": filters.finance_book,
		"cost_center": filters.cost_center,
		"project": filters.project,
		"include_default_book_entries": 1,
		"show_net_values": 1,
		"show_group_accounts": 1,
		"show_zero_values": filters.get("show_zero_values", 0),
		"with_period_closing_entry_for_opening": 1,
		"with_period_closing_entry_for_current_period": 1,
	})
	columns, data = execute_trial_balance(native_filters)
	return columns, data


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

	# The small-enterprise statutory form presents liabilities from the top and
	# fills the owners' equity section upward from the bottom.  Keeping its footer
	# aligned with "资产合计" also makes the accounting equation auditable on paper.
	equity_start = next(
		(index for index, row in enumerate(liability_equity_rows) if row.get("row_code") == "OWNERS_EQUITY_HEADING"),
		None,
	)
	if equity_start is not None:
		liability_rows = liability_equity_rows[:equity_start]
		equity_rows = liability_equity_rows[equity_start:]
		row_count = max(len(asset_rows), len(liability_equity_rows))
		liability_equity_rows = liability_rows + ([{}] * max(0, row_count - len(liability_rows) - len(equity_rows))) + equity_rows
	paired_rows = []
	for index in range(max(len(asset_rows), len(liability_equity_rows))):
		asset = asset_rows[index] if index < len(asset_rows) else {}
		liability_equity = liability_equity_rows[index] if index < len(liability_equity_rows) else {}
		paired_rows.append({
			"indent": max(asset.get("indent", 0), liability_equity.get("indent", 0)),
			"asset_label": asset.get("label"),
			"asset_statutory_line_number": asset.get("statutory_line_number"),
			"asset_row_type": asset.get("row_type"),
			"asset_opening_amount": asset.get("opening_amount"),
			"asset_amount": asset.get("amount"),
			"asset_comparison_amount": asset.get("comparison_amount"),
			"asset_indent": asset.get("indent", 0),
			"asset_bold": asset.get("bold", 0),
			"liability_equity_label": liability_equity.get("label"),
			"liability_equity_statutory_line_number": liability_equity.get("statutory_line_number"),
			"liability_equity_row_type": liability_equity.get("row_type"),
			"liability_equity_opening_amount": liability_equity.get("opening_amount"),
			"liability_equity_amount": liability_equity.get("amount"),
			"liability_equity_comparison_amount": liability_equity.get("comparison_amount"),
			"liability_equity_indent": liability_equity.get("indent", 0),
			"liability_equity_bold": liability_equity.get("bold", 0),
		})
	return paired_rows


@frappe.whitelist()
def export_current_report_pdf(filters=None):
	"""Generate a report PDF on the server without Query Report's print dialog.

	Frappe 16's browser-side query-report print template path is not compatible
	with this report's custom balance-sheet rendering.  This endpoint renders the
	actual report result directly, so the exported values always match the page.
	"""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = frappe._dict(filters or {})
	if not filters.company:
		frappe.throw(_("请选择公司"))
	frappe.has_permission("Company", doc=filters.company, throw=True)

	columns, rows, message, *_ = execute(filters)
	filters = frappe._dict(filters)
	_apply_default_period(filters)
	html = _render_report_pdf(filters, columns, rows, message)
	statement_title = _statement_title(filters.statement_type)
	filename = f"{statement_title}-{filters.company}-{filters.to_date}.pdf"
	file_doc = save_file(filename, get_pdf(html), "Company", filters.company, is_private=1)
	return {"file_url": file_doc.file_url, "file_name": file_doc.file_name}


def _statement_title(statement_type):
	return {
		"Balance Sheet": _("资产负债表"),
		"Profit and Loss": _("利润表"),
		"Cash Flow": _("现金流量表"),
		"Changes in Equity": _("所有者权益变动表"),
		"Trial Balance": _("试算平衡表"),
	}.get(statement_type, _("中国财务报表"))


FORM_CODES = {
	"企业会计准则": {
		"Balance Sheet": "会企01表",
		"Profit and Loss": "会企02表",
		"Cash Flow": "会企03表",
		"Changes in Equity": "会企04表",
	},
	"小企业会计准则": {
		"Balance Sheet": "会小企01表",
		"Profit and Loss": "会小企02表",
		"Cash Flow": "会小企03表",
		"Changes in Equity": "会小企04表",
	},
}


def _render_report_pdf(filters, columns, rows, message):
	"""Render the current report data into a self-contained printable document."""
	statement_type = filters.statement_type
	template = get_template(filters.company, statement_type, filters.to_date, required=False)
	standard = template.accounting_standard if template else ""
	title = _statement_title(statement_type)
	form_code = FORM_CODES.get(standard, {}).get(statement_type, "")

	escape = frappe.utils.escape_html
	tax_id = frappe.get_cached_value("Company", filters.company, "tax_id") or ""
	meta = (
		"<table class='meta'>"
		f"<tr><td>{escape(form_code)}</td><td class='right'>税款所属期起止：{filters.from_date} 至 {filters.to_date}</td></tr>"
		f"<tr><td>纳税人识别号：{escape(tax_id)}</td><td class='right'>报送日期：{nowdate()}</td></tr>"
		f"<tr><td>编制单位：{escape(filters.company)}</td><td class='right'>单位：元</td></tr>"
		"</table>"
	)
	if statement_type == "Balance Sheet":
		body = _render_balance_sheet_pdf_rows(rows)
	else:
		body = _render_standard_pdf_rows(columns, rows)
	warning = f"<p class='notice'>{message}</p>" if message else ""
	return f"""
	<!doctype html><html><head><meta charset='utf-8'>
	<style>
	@page {{ size: A4 landscape; margin: 12mm; }}
	body {{ font-family: 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif; font-size: 9pt; color: #111; }}
	h1 {{ text-align:center; font-size:16pt; margin:0 0 8px; }}
	.meta {{ width:100%; border-collapse:collapse; margin-bottom:8px; }}
	.meta td {{ font-size:9pt; padding:1px 0; }}
	.meta td.right {{ text-align:right; }}
	.notice {{ color:#666; font-size:8pt; }} table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
	th, td {{ border:1px solid #777; padding:5px 6px; vertical-align:middle; }} th {{ background:#f2f2f2; text-align:center; }}
	td.num {{ text-align:right; white-space:nowrap; }} td.line {{ text-align:center; width:36px; }}
	tr.bold td {{ font-weight:700; }}
	</style></head><body><h1>{title}</h1>{meta}{warning}{body}</body></html>
	"""


def _amount(value):
	return f"{flt(value):,.2f}"


def _render_balance_sheet_pdf_rows(rows):
	parts = [
		"<table><thead><tr><th>项目</th><th>行次</th><th>期末余额</th><th>年初余额</th>"
		"<th>负债和所有者权益</th><th>行次</th><th>期末余额</th><th>年初余额</th></tr></thead><tbody>"
	]
	for row in rows:
		asset_label = frappe.utils.escape_html(str(row.get("asset_label") or ""))
		liability_label = frappe.utils.escape_html(str(row.get("liability_equity_label") or ""))
		if row.get("asset_row_type") == "Heading" and asset_label:
			asset_label += "："
		if row.get("liability_equity_row_type") == "Heading" and liability_label:
			liability_label += "："
		bold = " class='bold'" if row.get("asset_bold") or row.get("liability_equity_bold") else ""
		asset_indent = int(row.get("asset_indent") or 0) * 12
		liability_indent = int(row.get("liability_equity_indent") or 0) * 12
		asset_opening = "" if row.get("asset_row_type") == "Heading" else _amount(row.get("asset_opening_amount"))
		asset_amount = "" if row.get("asset_row_type") == "Heading" else _amount(row.get("asset_amount"))
		liability_opening = "" if row.get("liability_equity_row_type") == "Heading" else _amount(row.get("liability_equity_opening_amount"))
		liability_amount = "" if row.get("liability_equity_row_type") == "Heading" else _amount(row.get("liability_equity_amount"))
		parts.append(
			f"<tr{bold}><td style='padding-left:{asset_indent + 6}px'>{asset_label}</td><td class='line'>{row.get('asset_statutory_line_number') or ''}</td>"
			f"<td class='num'>{asset_amount}</td><td class='num'>{asset_opening}</td>"
			f"<td style='padding-left:{liability_indent + 6}px'>{liability_label}</td><td class='line'>{row.get('liability_equity_statutory_line_number') or ''}</td>"
			f"<td class='num'>{liability_amount}</td><td class='num'>{liability_opening}</td></tr>"
		)
	parts.append("</tbody></table>")
	return "".join(parts)


def _render_standard_pdf_rows(columns, rows):
	visible_columns = [column for column in columns if column.get("fieldname")]
	head = "".join(f"<th>{frappe.utils.escape_html(str(column.get('label') or ''))}</th>" for column in visible_columns)
	parts = [f"<table><thead><tr>{head}</tr></thead><tbody>"]
	for row in rows:
		is_bold = " class='bold'" if row.get("bold") else ""
		cells = []
		for column in visible_columns:
			fieldname = column["fieldname"]
			value = row.get(fieldname, "")
			if column.get("fieldtype") in {"Currency", "Float", "Int"}:
				cells.append(f"<td class='num'>{_amount(value)}</td>")
			else:
				indent = "&nbsp;" * (int(row.get("indent") or 0) * 4)
				cells.append(f"<td>{indent}{frappe.utils.escape_html(str(value or ''))}</td>")
		parts.append(f"<tr{is_bold}>{''.join(cells)}</tr>")
	parts.append("</tbody></table>")
	return "".join(parts)


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


def get_cash_flow_dashboard_metrics(rows, company, filters):
	metrics = get_cash_flow_metrics(rows)
	closing_balance_sheet = build_statement(
		company,
		"Balance Sheet",
		filters.from_date,
		filters.to_date,
		filters.finance_book,
		filters.cost_center,
		filters.project,
	)
	balance_amounts = {row["row_code"]: flt(row.get("amount")) for row in closing_balance_sheet["rows"]}
	return {
		"operating": metrics["operating"],
		"cash_balance": flt(next(
			(row.get("amount") for row in rows if row.get("row_code") == "CLOSING_CASH"),
			0,
		)),
		"accounts_receivable": balance_amounts.get("ACCOUNTS_RECEIVABLE", 0),
		"inventory": balance_amounts.get("INVENTORIES", 0),
	}


def get_cash_flow_chart(rows, company, filters):
	metrics = get_cash_flow_dashboard_metrics(rows, company, filters)
	period_label = filters.get("accounting_period") or filters.get("to_date")
	return {
		"data": {
			"labels": [period_label],
			"datasets": [
				{"name": _("经营现金流"), "values": [metrics["operating"]]},
				{"name": _("期末现金及现金等价物"), "values": [metrics["cash_balance"]]},
				{"name": _("应收账款"), "values": [metrics["accounts_receivable"]]},
				{"name": _("存货"), "values": [metrics["inventory"]]},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"colors": ["#16a34a", "#2563eb", "#f59e0b", "#e76f51"],
	}


def get_cash_flow_summary(rows, company, filters):
	metrics = get_cash_flow_dashboard_metrics(rows, company, filters)
	currency = frappe.get_cached_value("Company", company, "default_currency")
	return [
		{
			"value": metrics["operating"],
			"label": _("经营活动产生的现金流量净额"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if metrics["operating"] >= 0 else "Red",
		},
		{
			"value": metrics["cash_balance"],
			"label": _("期末现金及现金等价物余额"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": metrics["accounts_receivable"],
			"label": _("应收账款余额"),
			"datatype": "Currency",
			"currency": currency,
		},
		{
			"value": metrics["inventory"],
			"label": _("存货余额"),
			"datatype": "Currency",
			"currency": currency,
		},
	]
