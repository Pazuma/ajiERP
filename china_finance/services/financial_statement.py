import ast
import hashlib
import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, getdate


ALLOWED_AST_NODES = (
	ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub, ast.Mult, ast.Div,
	ast.USub, ast.UAdd, ast.Constant, ast.Name, ast.Load,
)


def validate_formula(formula, valid_codes):
	if not formula:
		frappe.throw(_("公式行必须填写公式"))
	try:
		tree = ast.parse(formula, mode="eval")
	except SyntaxError:
		frappe.throw(_("报表公式语法错误：{0}").format(formula))
	for node in ast.walk(tree):
		if not isinstance(node, ALLOWED_AST_NODES):
			frappe.throw(_("报表公式包含不允许的表达式"))
		if isinstance(node, ast.Name) and node.id not in valid_codes:
			frappe.throw(_("报表公式引用了不存在的行：{0}").format(node.id))
	return tree


def evaluate_formula(formula, values):
	tree = validate_formula(formula, set(values))
	return flt(eval(compile(tree, "<china-finance-formula>", "eval"), {"__builtins__": {}}, values), 2)


def get_formula_dependencies(formula, valid_codes):
	tree = validate_formula(formula, valid_codes)
	return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def validate_formula_graph(rows):
	valid_codes = {row.row_code for row in rows}
	dependencies = {
		row.row_code: get_formula_dependencies(row.formula, valid_codes)
		for row in rows if row.row_type == "Formula"
	}
	resolved = {row.row_code for row in rows if row.row_type != "Formula"}
	while dependencies:
		ready = [code for code, refs in dependencies.items() if refs <= resolved]
		if not ready:
			frappe.throw(_("报表公式存在循环引用或不确定的前向依赖：{0}").format(", ".join(sorted(dependencies))))
		for code in ready:
			resolved.add(code)
			dependencies.pop(code)


def get_template(company, statement_type, to_date, accounting_standard=None, required=True):
	to_date = getdate(to_date)
	if not accounting_standard:
		accounting_standard = frappe.get_cached_doc("China Finance Settings", company).accounting_standard
	filters = {
		"accounting_standard": accounting_standard, "statement_type": statement_type,
		"is_active": 1, "effective_from": ["<=", to_date],
	}
	name = next(
		(
			row.name
			for row in frappe.get_all(
				"China Financial Statement Template", filters=filters,
				fields=["name", "effective_to"], order_by="effective_from desc, version desc",
			)
			if not row.effective_to or getdate(row.effective_to) >= to_date
		),
		None,
	)
	if not name:
		if required:
			frappe.throw(_("未找到适用于 {0} 的 {1} 报表模板").format(accounting_standard, statement_type))
		return None
	return frappe.get_cached_doc("China Financial Statement Template", name)


def build_statement(company, statement_type, from_date, to_date, finance_book=None, cost_center=None, project=None):
	to_date = getdate(to_date)
	from_date = getdate(from_date or get_first_day(to_date))
	template = get_template(company, statement_type, to_date)
	mappings = get_mappings(company, template, to_date)
	year_start = get_fiscal_year_start(company, to_date)

	if statement_type == "Cash Flow":
		period_values, period_meta = get_cash_flow_values(
			company, mappings, from_date, to_date, finance_book, cost_center, project
		)
		ytd_values, ytd_meta = get_cash_flow_values(
			company, mappings, year_start, to_date, finance_book, cost_center, project
		)
		opening_values = None
	else:
		period_values = get_statement_values(
			company, mappings, statement_type, from_date, to_date, finance_book, cost_center, project, template=template
		)
		ytd_values = get_statement_values(
			company, mappings, statement_type, year_start, to_date, finance_book, cost_center, project, template=template
		)
		opening_values = (
			get_statement_values(
				company, mappings, statement_type, None, add_days(from_date, -1), finance_book, cost_center, project,
				as_at_date=True, template=template,
			)
			if statement_type in {"Balance Sheet", "Changes in Equity"} else None
		)
		period_meta = ytd_meta = {}

	period_rows = render_rows(template, period_values)
	opening_rows = (
		{row["row_code"]: row["amount"] for row in render_rows(template, opening_values)}
		if opening_values is not None else {}
	)
	ytd_rows = {row["row_code"]: row["amount"] for row in render_rows(template, ytd_values)}
	for result_row in period_rows:
		result_row["opening_amount"] = opening_rows.get(result_row["row_code"]) if opening_values is not None else None
		result_row["year_to_date_amount"] = (
			ytd_rows.get(result_row["row_code"], 0) if statement_type != "Balance Sheet" else None
		)
	cash_flow_supplement = []
	cash_equivalent_composition = []
	equity_matrix = None
	if statement_type == "Cash Flow":
		cash_flow_supplement = build_cash_flow_supplement(
			company, from_date, to_date, period_rows, finance_book, cost_center, project
		)
		cash_equivalent_composition = build_cash_equivalent_composition(
			company, from_date, to_date, finance_book, cost_center, project
		)
	elif statement_type == "Changes in Equity":
		equity_matrix = build_equity_matrix(
			company, template, mappings, from_date, to_date, finance_book, cost_center, project
		)

	warnings = []
	if not mappings:
		warnings.append(_("该公司尚未配置报表科目映射"))
	unreviewed = sum(1 for mapping in mappings if not mapping.reviewed)
	if unreviewed:
		warnings.append(_("有 {0} 条自动科目映射尚未复核").format(unreviewed))
	if statement_type == "Balance Sheet":
		temporary_inventory_accrual_debit = get_temporary_inventory_accrual_debit_balance(
			company, to_date, finance_book, cost_center, project
		)
		if temporary_inventory_accrual_debit:
			warnings.append(
				_("暂估应付款存在借方余额 {0}，已重分类至其他流动资产；请完成采购入库或核对该采购发票。").format(
					temporary_inventory_accrual_debit
				)
			)
	if period_meta.get("unclassified_amount"):
		warnings.append(_("本期有未分类现金流 {0}").format(period_meta["unclassified_amount"]))
	if ytd_meta.get("unclassified_amount") and year_start != from_date:
		warnings.append(_("本年累计有未分类现金流 {0}").format(ytd_meta["unclassified_amount"]))
	if period_meta.get("opening_entry_cash"):
		warnings.append(_("本期含开账现金 {0}，已计入期初余额而未计入经营现金流").format(period_meta["opening_entry_cash"]))
	if statement_type == "Cash Flow":
		if period_meta.get("manual_assignment_count"):
			warnings.append(_("本期已按凭证直接指定取数 {0} 张").format(period_meta["manual_assignment_count"]))
		if period_meta.get("automatic_transaction_count"):
			warnings.append(_("本期仍按科目映射自动补充 {0} 张").format(period_meta["automatic_transaction_count"]))
		from china_finance.services.cash_flow_assignment import get_assignment_coverage

		coverage = get_assignment_coverage(company, from_date, to_date)
		if coverage["count"]:
			warnings.append(coverage["details"])
	return {
		"template": template.name, "template_version": template.version, "accounting_standard": template.accounting_standard,
		"from_date": str(from_date), "to_date": str(to_date), "fiscal_year_start": str(year_start),
		"rows": period_rows, "warnings": warnings, "cash_flow_meta": period_meta,
		"cash_flow_supplement": cash_flow_supplement,
		"cash_equivalent_composition": cash_equivalent_composition,
		"equity_matrix": equity_matrix,
		"report_status": "草表", "amount_unit": frappe.db.get_value("China Finance Settings", company, "report_amount_unit") or "元",
	}


def get_mappings(company, template, to_date):
	mappings = frappe.get_all(
		"China Financial Statement Mapping",
		filters={"company": company, "template": template.name, "effective_from": ["<=", to_date]},
		fields=[
			"name", "row_code", "account", "sign_multiplier", "reviewed", "effective_from", "effective_to",
			"cash_inflow_row_code", "cash_outflow_row_code",
		],
	)
	active = {}
	for row in sorted(mappings, key=lambda item: getdate(item.effective_from), reverse=True):
		if row.account in active or (row.effective_to and getdate(row.effective_to) < to_date):
			continue
		active[row.account] = row
	return list(active.values())


def get_mapping_revisions(company, template, from_date, to_date):
	"""Return every mapping revision that overlaps the requested movement period."""
	rows = frappe.get_all(
		"China Financial Statement Mapping",
		filters={
			"company": company,
			"template": template.name,
			"effective_from": ["<=", to_date],
		},
		fields=[
			"name", "row_code", "account", "sign_multiplier", "reviewed", "effective_from", "effective_to",
			"cash_inflow_row_code", "cash_outflow_row_code",
		],
		order_by="account, effective_from",
	)
	return [row for row in rows if not row.effective_to or getdate(row.effective_to) >= getdate(from_date)]


def get_mapping_for_date(revisions_by_account, account, posting_date):
	posting_date = getdate(posting_date)
	for mapping in revisions_by_account.get(account, ()):
		if getdate(mapping.effective_from) <= posting_date and (
			not mapping.effective_to or getdate(mapping.effective_to) >= posting_date
		):
			return mapping
	return None


def get_period_mapped_values(
	company, template, from_date, to_date, finance_book=None, cost_center=None, project=None, skip_codes=None,
	exclude_period_closing=False,
):
	"""Split movement amounts at mapping effective-date boundaries."""
	values = defaultdict(float)
	skip_codes = set(skip_codes or ())
	for mapping in get_mapping_revisions(company, template, from_date, to_date):
		if mapping.row_code in skip_codes:
			continue
		mapping_from = max(getdate(from_date), getdate(mapping.effective_from))
		mapping_to = min(
			getdate(to_date), getdate(mapping.effective_to) if mapping.effective_to else getdate(to_date)
		)
		if mapping_from > mapping_to:
			continue
		balance = get_account_balances(
			company, [mapping.account], mapping_from, mapping_to, finance_book, cost_center, project,
			exclude_period_closing=exclude_period_closing,
		).get(mapping.account, 0)
		value = flt(balance) * int(mapping.sign_multiplier)
		if get_mapping_direction(template, mapping.row_code) == "Credit Positive":
			value = -value
		values[mapping.row_code] += value
	return values


def render_rows(template, source_values):
	values = defaultdict(float, source_values or {})
	valid_codes = {row.row_code for row in template.rows}
	for code in valid_codes:
		values[code] += 0
	validate_formula_graph(template.rows)
	pending = {row.row_code: row for row in template.rows if row.row_type == "Formula"}
	resolved = {row.row_code for row in template.rows if row.row_type != "Formula"}
	while pending:
		progress = False
		for code, template_row in list(pending.items()):
			dependencies = get_formula_dependencies(template_row.formula, valid_codes)
			if dependencies <= resolved:
				values[code] = evaluate_formula(template_row.formula, values)
				resolved.add(code)
				del pending[code]
				progress = True
		if not progress:
			frappe.throw(_("报表公式存在循环引用或无法确定的依赖：{0}").format(", ".join(sorted(pending))))
	rows = []
	for template_row in template.rows:
		value = flt(values[template_row.row_code], 2)
		values[template_row.row_code] = value
		if template_row.show_zero or value or template_row.row_type == "Heading":
			rows.append(
				{
					"row_code": template_row.row_code, "label": template_row.label, "amount": value,
					"indent": template_row.indent, "bold": template_row.bold,
					"row_type": template_row.row_type, "statutory_line_number": template_row.statutory_line_number,
				}
			)
	return rows


def get_statement_values(
	company, mappings, statement_type, from_date, to_date, finance_book=None, cost_center=None, project=None,
	as_at_date=False, template=None
):
	if not as_at_date and statement_type in {"Profit and Loss", "Changes in Equity"}:
		values = get_period_mapped_values(
			company, template, from_date, to_date, finance_book, cost_center, project,
			skip_codes={"OPENING_EQUITY", "NET_PROFIT", "CLOSING_EQUITY"},
			exclude_period_closing=statement_type == "Profit and Loss",
		)
		if statement_type == "Changes in Equity":
			period_from = from_date or get_fiscal_year_start(company, to_date)
			values["OPENING_EQUITY"] = get_owner_equity_balance(
				company, add_days(period_from, -1), finance_book, cost_center, project
			)
			values["NET_PROFIT"] = get_net_profit(
				company, period_from, to_date, finance_book, cost_center, project
			)
		return values

	accounts = list({row.account for row in mappings})
	temporary_inventory_accrual_account = (
		frappe.get_cached_value("Company", company, "stock_received_but_not_billed")
		if statement_type == "Balance Sheet"
		else None
	)
	if temporary_inventory_accrual_account and temporary_inventory_accrual_account not in accounts:
		accounts.append(temporary_inventory_accrual_account)
	balances = get_account_balances(
		company, accounts, None if as_at_date or statement_type == "Balance Sheet" else from_date, to_date,
		finance_book, cost_center, project,
	)
	values = defaultdict(float)
	vat_accounts = get_active_vat_accounts(company, to_date) if statement_type == "Balance Sheet" else set()
	temporary_inventory_accrual_debit = max(
		flt(balances.get(temporary_inventory_accrual_account)), 0
	) if temporary_inventory_accrual_account else 0
	vat_balance = 0
	for mapping in mappings:
		if statement_type == "Changes in Equity" and mapping.row_code in {"OPENING_EQUITY", "NET_PROFIT", "CLOSING_EQUITY"}:
			continue
		if mapping.row_code == "TAXES_PAYABLE" and mapping.account in vat_accounts:
			vat_balance += flt(balances.get(mapping.account))
			continue
		# Invoice-before-receipt entries can leave Stock Received But Not Billed
		# with a debit balance. That is an unsettled current asset, not a negative
		# payable that offsets the supplier liability.
		if mapping.account == temporary_inventory_accrual_account and flt(balances.get(mapping.account)) > 0:
			continue
		value = flt(balances.get(mapping.account)) * int(mapping.sign_multiplier)
		if get_mapping_direction(template, mapping.row_code) == "Credit Positive":
			value = -value
		values[mapping.row_code] += value
	if statement_type == "Balance Sheet":
		apply_vat_net_presentation(values, vat_balance)
		apply_temporary_inventory_accrual_presentation(values, temporary_inventory_accrual_debit)
		values["RETAINED_EARNINGS"] += get_unclosed_profit(
			company, to_date, finance_book, cost_center, project
		)

	if statement_type == "Changes in Equity":
		if as_at_date:
			values["OPENING_EQUITY"] = get_owner_equity_balance(company, to_date, finance_book, cost_center, project)
			values["NET_PROFIT"] = 0
			return values
	return values


def get_active_vat_accounts(company, as_at_date):
	"""Return effective input/output VAT accounts configured for the company."""
	as_at_date = getdate(as_at_date)
	rows = frappe.get_all(
		"China Tax Account Mapping",
		filters={"company": company, "enabled": 1, "direction": ["in", ("Input", "Output")]},
		fields=["account", "effective_from", "effective_to"],
	)
	return {
		row.account
		for row in rows
		if getdate(row.effective_from) <= as_at_date
		and (not row.effective_to or getdate(row.effective_to) >= as_at_date)
	}


def apply_vat_net_presentation(values, vat_balance):
	"""Present net VAT as an asset when deductible, otherwise as tax payable.

	Input and output VAT remain ERPNext liability-root accounts for posting and
	tax reconciliation. A debit net balance is not a negative liability in a
	Chinese balance sheet: it is a deductible VAT asset presented in other
	current assets.
	"""
	vat_balance = flt(vat_balance)
	if vat_balance > 0:
		values["OTHER_CURRENT_ASSETS"] += vat_balance
	elif vat_balance < 0:
		values["TAXES_PAYABLE"] += -vat_balance


def apply_temporary_inventory_accrual_presentation(values, debit_balance):
	"""Present a debit Stock Received But Not Billed balance as a current asset."""
	if debit_balance:
		values["OTHER_CURRENT_ASSETS"] += debit_balance


def get_temporary_inventory_accrual_debit_balance(
	company, as_at_date, finance_book=None, cost_center=None, project=None
):
	account = frappe.get_cached_value("Company", company, "stock_received_but_not_billed")
	if not account:
		return 0
	balance = get_account_balances(
		company, [account], None, as_at_date, finance_book, cost_center, project
	).get(account, 0)
	return max(flt(balance), 0)


def get_mapping_direction(template, row_code):
	if not template:
		return "Debit Positive"
	return next(
		(row.balance_direction for row in template.rows if row.row_code == row_code),
		"Debit Positive",
	)


def get_cash_flow_values(company, mappings, from_date, to_date, finance_book=None, cost_center=None, project=None):
	from china_finance.services.cash_flow_assignment import get_confirmed_cash_flow_values
	from china_finance.services.cash_equivalent_scope import get_cash_scope_accounts

	confirmed_values, confirmed_sources, _confirmed_entries = get_confirmed_cash_flow_values(
		company, from_date, to_date, finance_book, cost_center, project
	)
	values = defaultdict(float, confirmed_values)
	revisions_by_account = defaultdict(list)
	for mapping in get_mapping_revisions(company, get_template(company, "Cash Flow", to_date), from_date, to_date):
		revisions_by_account[mapping.account].append(mapping)
	conditions, parameters = get_gl_conditions(company, from_date, to_date, finance_book, cost_center, project)
	conditions.append("gle.is_opening='No'")
	cash_accounts = get_cash_scope_accounts(company, to_date)
	if not cash_accounts:
		return values, {
			"unclassified_amount": 0, "transaction_count": len(confirmed_sources),
			"manual_assignment_count": len(confirmed_sources), "automatic_transaction_count": 0,
			"opening_entry_cash": 0, "cash_scope_missing": 1,
		}
	parameters["cash_accounts"] = cash_accounts
	cash_rows = frappe.db.sql(
		f"""
		SELECT gle.voucher_type, gle.voucher_no, MIN(gle.posting_date) AS posting_date,
			SUM(gle.debit - gle.credit) AS cash_change
		FROM `tabGL Entry` gle
		WHERE {' AND '.join(conditions)} AND gle.account IN %(cash_accounts)s
		GROUP BY gle.voucher_type, gle.voucher_no
		HAVING ABS(cash_change) > 0.000001
		""",
		parameters, as_dict=True,
	)
	unclassified = 0.0
	automatic_transaction_count = 0
	for cash_row in cash_rows:
		if (cash_row.voucher_type, cash_row.voucher_no) in confirmed_sources:
			continue
		automatic_transaction_count += 1
		counterpart_conditions = [
			"gle.company=%(company)s", "gle.voucher_type=%(voucher_type)s", "gle.voucher_no=%(voucher_no)s",
			"gle.is_cancelled=0", "gle.is_opening='No'",
		]
		counterpart_values = {
			"company": company, "voucher_type": cash_row.voucher_type, "voucher_no": cash_row.voucher_no,
			"cash_accounts": cash_accounts,
		}
		for fieldname, value in (("finance_book", finance_book), ("cost_center", cost_center), ("project", project)):
			if value:
				counterpart_conditions.append(f"gle.{fieldname}=%({fieldname})s")
				counterpart_values[fieldname] = value
		counterparts = frappe.db.sql(
			f"""
			SELECT gle.account, SUM(gle.debit - gle.credit) AS movement
			FROM `tabGL Entry` gle
			WHERE {' AND '.join(counterpart_conditions)} AND gle.account NOT IN %(cash_accounts)s
			GROUP BY gle.account
			HAVING ABS(movement) > 0.000001
			""",
			counterpart_values, as_dict=True,
		)
		total_weight = sum(abs(flt(row.movement)) for row in counterparts)
		if not total_weight:
			continue
		for counterpart in counterparts:
			allocated = flt(cash_row.cash_change) * abs(flt(counterpart.movement)) / total_weight
			mapping = get_mapping_for_date(
				revisions_by_account, counterpart.account, cash_row.posting_date
			)
			row_code = None
			if mapping:
				row_code = mapping.cash_inflow_row_code if allocated > 0 else mapping.cash_outflow_row_code
			if row_code:
				values[row_code] += allocated if row_code == "FX_EFFECT" else abs(allocated)
			else:
				unclassified += allocated

	opening_entry_cash = get_opening_entry_cash(company, from_date, to_date, finance_book, cost_center, project, cash_accounts)
	values["OPENING_CASH"] = (
		get_cash_balance(company, add_days(from_date, -1), finance_book, cost_center, project, cash_accounts) + opening_entry_cash
	)
	values["CLOSING_CASH"] = get_cash_balance(company, to_date, finance_book, cost_center, project, cash_accounts)
	return values, {
		"unclassified_amount": flt(unclassified, 2),
		"transaction_count": automatic_transaction_count + len(confirmed_sources),
		"manual_assignment_count": len(confirmed_sources),
		"automatic_transaction_count": automatic_transaction_count,
		"opening_entry_cash": flt(opening_entry_cash, 2),
	}


def get_opening_entry_cash(company, from_date, to_date, finance_book=None, cost_center=None, project=None, cash_accounts=None):
	"""Treat opening-entry cash posted in the selected range as opening balance, not cash movement."""
	conditions, parameters = get_gl_conditions(company, from_date, to_date, finance_book, cost_center, project)
	conditions.append("gle.is_opening='Yes'")
	if cash_accounts is None:
		from china_finance.services.cash_equivalent_scope import get_cash_scope_accounts
		cash_accounts = get_cash_scope_accounts(company, to_date)
	if not cash_accounts:
		return 0
	parameters["cash_accounts"] = cash_accounts
	return flt(
		frappe.db.sql(
			f"""
			SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
			FROM `tabGL Entry` gle
			WHERE {' AND '.join(conditions)} AND gle.account IN %(cash_accounts)s
			""",
			parameters,
		)[0][0]
	)


def get_gl_conditions(company, from_date, to_date, finance_book=None, cost_center=None, project=None):
	conditions = [
		"gle.company=%(company)s", "gle.posting_date>=%(from_date)s", "gle.posting_date<=%(to_date)s",
		"gle.is_cancelled=0",
	]
	values = {"company": company, "from_date": from_date, "to_date": to_date}
	if finance_book:
		conditions.append("gle.finance_book=%(finance_book)s")
		values["finance_book"] = finance_book
	if cost_center:
		conditions.append("gle.cost_center=%(cost_center)s")
		values["cost_center"] = cost_center
	if project:
		conditions.append("gle.project=%(project)s")
		values["project"] = project
	return conditions, values


def get_account_balances(
	company, accounts, from_date, to_date, finance_book=None, cost_center=None, project=None,
	exclude_period_closing=False,
):
	if not accounts:
		return {}
	conditions = ["company=%(company)s", "account IN %(accounts)s", "posting_date<=%(to_date)s", "is_cancelled=0"]
	values = {"company": company, "accounts": accounts, "to_date": to_date}
	if from_date:
		conditions.append("posting_date>=%(from_date)s")
		values["from_date"] = from_date
	if finance_book:
		conditions.append("finance_book=%(finance_book)s")
		values["finance_book"] = finance_book
	if cost_center:
		conditions.append("cost_center=%(cost_center)s")
		values["cost_center"] = cost_center
	if project:
		conditions.append("project=%(project)s")
		values["project"] = project
	if exclude_period_closing:
		conditions.append("voucher_type!='Period Closing Voucher'")
	rows = frappe.db.sql(
		f"SELECT account, SUM(debit-credit) AS balance FROM `tabGL Entry` WHERE {' AND '.join(conditions)} GROUP BY account",
		values, as_dict=True,
	)
	return {row.account: row.balance for row in rows}


def get_cash_balance(company, to_date, finance_book=None, cost_center=None, project=None, cash_accounts=None):
	conditions = ["gle.company=%(company)s", "gle.posting_date<=%(to_date)s", "gle.is_cancelled=0"]
	values = {"company": company, "to_date": to_date}
	if cash_accounts is None:
		from china_finance.services.cash_equivalent_scope import get_cash_scope_accounts
		cash_accounts = get_cash_scope_accounts(company, to_date)
	if not cash_accounts:
		return 0
	values["cash_accounts"] = cash_accounts
	if finance_book:
		conditions.append("gle.finance_book=%(finance_book)s")
		values["finance_book"] = finance_book
	if cost_center:
		conditions.append("gle.cost_center=%(cost_center)s")
		values["cost_center"] = cost_center
	if project:
		conditions.append("gle.project=%(project)s")
		values["project"] = project
	return flt(
		frappe.db.sql(
			f"""SELECT COALESCE(SUM(gle.debit-gle.credit), 0) FROM `tabGL Entry` gle
			WHERE {' AND '.join(conditions)} AND gle.account IN %(cash_accounts)s""",
			values,
		)[0][0],
		2,
	)


def get_owner_equity_balance(company, to_date, finance_book=None, cost_center=None, project=None):
	conditions = ["gle.company=%(company)s", "gle.posting_date<=%(to_date)s", "gle.is_cancelled=0"]
	values = {"company": company, "to_date": to_date}
	if finance_book:
		conditions.append("gle.finance_book=%(finance_book)s")
		values["finance_book"] = finance_book
	if cost_center:
		conditions.append("gle.cost_center=%(cost_center)s")
		values["cost_center"] = cost_center
	if project:
		conditions.append("gle.project=%(project)s")
		values["project"] = project
	amount = frappe.db.sql(
		f"""SELECT COALESCE(SUM(gle.debit-gle.credit), 0) FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` account ON account.name=gle.account
		WHERE {' AND '.join(conditions)} AND account.root_type IN ('Equity', 'Income', 'Expense')""",
		values,
	)[0][0]
	return -flt(amount, 2)


def get_net_profit(company, from_date, to_date, finance_book=None, cost_center=None, project=None):
	conditions, values = get_gl_conditions(company, from_date, to_date, finance_book, cost_center, project)
	amount = frappe.db.sql(
		f"""SELECT COALESCE(SUM(gle.credit-gle.debit), 0) FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` account ON account.name=gle.account
		WHERE {' AND '.join(conditions)} AND account.root_type IN ('Income', 'Expense')
		AND gle.voucher_type!='Period Closing Voucher'""",
		values,
	)[0][0]
	return flt(amount, 2)


def get_unclosed_profit(company, to_date, finance_book=None, cost_center=None, project=None):
	"""Return income/expense balances still open at the reporting date."""
	conditions = ["gle.company=%(company)s", "gle.posting_date<=%(to_date)s", "gle.is_cancelled=0"]
	values = {"company": company, "to_date": to_date}
	for fieldname, value in (("finance_book", finance_book), ("cost_center", cost_center), ("project", project)):
		if value:
			conditions.append(f"gle.{fieldname}=%({fieldname})s")
			values[fieldname] = value
	amount = frappe.db.sql(
		f"""SELECT COALESCE(SUM(gle.credit-gle.debit), 0)
		FROM `tabGL Entry` gle INNER JOIN `tabAccount` account ON account.name=gle.account
		WHERE {' AND '.join(conditions)} AND account.root_type IN ('Income', 'Expense')""",
		values,
	)[0][0]
	return flt(amount, 2)


def get_fiscal_year_start(company, to_date):
	from erpnext.accounts.utils import get_fiscal_year

	return getdate(get_fiscal_year(to_date, company=company)[1])


def get_comparison_period(company, statement_type, from_date, to_date):
	from frappe.utils import add_years

	from_date, to_date = getdate(from_date), getdate(to_date)
	if statement_type == "Balance Sheet":
		previous_end = add_days(get_fiscal_year_start(company, from_date), -1)
		return None, previous_end
	return add_years(from_date, -1), add_years(to_date, -1)


def build_cash_flow_supplement(company, from_date, to_date, cash_rows, finance_book=None, cost_center=None, project=None):
	"""Generate the mandatory indirect-method reconciliation without changing direct-method main statement."""
	amounts = {row["row_code"]: flt(row["amount"]) for row in cash_rows}
	net_profit = get_net_profit(company, from_date, to_date, finance_book, cost_center, project)
	operating_cash = amounts.get("OPERATING_CASH_FLOW", 0)
	known_adjustments = []
	for code, label, account_types in (
		("DEPRECIATION_AMORTIZATION", _("固定资产折旧、使用权资产折旧及无形资产摊销"), ("Depreciation", "Accumulated Depreciation")),
		("INVENTORY_CHANGE", _("存货变动"), ("Stock",)),
		("RECEIVABLE_CHANGE", _("经营性应收项目变动"), ("Receivable",)),
		("PAYABLE_CHANGE", _("经营性应付项目变动"), ("Payable",)),
	):
		value = get_account_type_movement(company, account_types, from_date, to_date, finance_book, cost_center, project)
		if code in {"INVENTORY_CHANGE", "RECEIVABLE_CHANGE"}:
			value = -value
		elif code == "PAYABLE_CHANGE":
			value = -value
		known_adjustments.append({"row_code": code, "label": label, "amount": flt(value, 2)})
	known_total = sum(row["amount"] for row in known_adjustments)
	other = flt(operating_cash - net_profit - known_total, 2)
	return [
		{"row_code": "NET_PROFIT", "label": _("净利润"), "amount": net_profit},
		*known_adjustments,
		{"row_code": "OTHER_OPERATING_ADJUSTMENTS", "label": _("其他经营性调整"), "amount": other},
		{"row_code": "INDIRECT_OPERATING_CASH_FLOW", "label": _("经营活动产生的现金流量净额"), "amount": operating_cash},
	]


def get_account_type_movement(company, account_types, from_date, to_date, finance_book=None, cost_center=None, project=None):
	conditions, values = get_gl_conditions(company, from_date, to_date, finance_book, cost_center, project)
	values["account_types"] = account_types
	return flt(frappe.db.sql(
		f"""SELECT COALESCE(SUM(gle.debit-gle.credit), 0) FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` account ON account.name=gle.account
		WHERE {' AND '.join(conditions)} AND account.account_type IN %(account_types)s""", values
	)[0][0], 2)


def build_cash_equivalent_composition(company, from_date, to_date, finance_book=None, cost_center=None, project=None):
	from china_finance.services.cash_equivalent_scope import get_effective_cash_scope

	result = []
	for scope in get_effective_cash_scope(company, to_date):
		if not scope.included or scope.classification == "排除项":
			continue
		opening = get_account_balances(
			company, [scope.account], None, add_days(from_date, -1), finance_book, cost_center, project
		).get(scope.account, 0) + get_account_opening_entries(
			company, [scope.account], from_date, to_date, finance_book, cost_center, project
		).get(scope.account, 0)
		closing = get_account_balances(
			company, [scope.account], None, to_date, finance_book, cost_center, project
		).get(scope.account, 0)
		result.append({
			"account": scope.account, "classification": scope.classification,
			"opening_amount": flt(opening, 2), "closing_amount": flt(closing, 2),
			"restricted": int(bool(scope.restricted)), "restriction_reason": scope.restriction_reason,
		})
	return result


EQUITY_COMPONENTS = (
	("paid_in_capital", "实收资本（或股本）"), ("capital_reserve", "资本公积"),
	("other_comprehensive_income", "其他综合收益"), ("special_reserve", "专项储备"),
	("surplus_reserve", "盈余公积"), ("retained_earnings", "未分配利润"),
)


def classify_equity_component(account_name):
	name = account_name or ""
	for component, words in (
		("paid_in_capital", ("实收资本", "股本")), ("capital_reserve", ("资本公积",)),
		("other_comprehensive_income", ("其他综合收益",)), ("special_reserve", ("专项储备",)),
		("surplus_reserve", ("盈余公积",)),
	):
		if any(word in name for word in words):
			return component
	return "retained_earnings"


def build_equity_matrix(company, template, mappings, from_date, to_date, finance_book=None, cost_center=None, project=None):
	accounts = frappe.get_all(
		"Account", filters={"company": company, "root_type": "Equity", "is_group": 0, "disabled": 0},
		fields=["name", "account_name"],
	)
	account_components = {row.name: classify_equity_component(row.account_name or row.name) for row in accounts}
	account_names = list(account_components)
	opening_balances = get_account_balances(
		company, account_names, None, add_days(from_date, -1), finance_book, cost_center, project
	)
	for account, value in get_account_opening_entries(
		company, account_names, from_date, to_date, finance_book, cost_center, project
	).items():
		opening_balances[account] = flt(opening_balances.get(account)) + flt(value)
	period_values = defaultdict(lambda: defaultdict(float))
	for mapping in get_mapping_revisions(company, template, from_date, to_date):
		if mapping.account not in account_components:
			continue
		mapping_from = max(getdate(from_date), getdate(mapping.effective_from))
		mapping_to = min(
			getdate(to_date), getdate(mapping.effective_to) if mapping.effective_to else getdate(to_date)
		)
		if mapping_from > mapping_to:
			continue
		amount = get_account_balances_excluding_opening(
			company, [mapping.account], mapping_from, mapping_to, finance_book, cost_center, project
		).get(mapping.account, 0)
		period_values[mapping.row_code][account_components[mapping.account]] += (
			-flt(amount) * int(mapping.sign_multiplier)
		)
	rows = []

	def blank(code, label, bold=0):
		return {"row_code": code, "label": label, "bold": bold, **{component: 0.0 for component, _label in EQUITY_COMPONENTS}}

	opening = blank("OPENING_EQUITY", "一、上年年末所有者权益余额", 1)
	for account, value in opening_balances.items():
		opening[account_components[account]] += -flt(value)
	rows.append(opening)

	for template_row in template.rows:
		if template_row.row_code in {"OPENING_EQUITY", "CURRENT_OPENING_EQUITY", "CURRENT_EQUITY_CHANGE", "CLOSING_EQUITY"}:
			continue
		matrix_row = blank(template_row.row_code, template_row.label, template_row.bold)
		if template_row.row_code == "NET_PROFIT":
			matrix_row["retained_earnings"] = get_net_profit(
				company, from_date, to_date, finance_book, cost_center, project
			)
		else:
			for component, value in period_values.get(template_row.row_code, {}).items():
				matrix_row[component] += value
		rows.append(matrix_row)

	closing = blank("CLOSING_EQUITY", "四、本年年末所有者权益余额", 1)
	for component, _label in EQUITY_COMPONENTS:
		closing[component] = sum(flt(row[component]) for row in rows)
	for row in [*rows, closing]:
		row["total"] = flt(sum(flt(row[component]) for component, _label in EQUITY_COMPONENTS), 2)
	return {"components": [{"fieldname": code, "label": label} for code, label in EQUITY_COMPONENTS], "rows": [*rows, closing]}


def get_account_opening_entries(company, accounts, from_date, to_date, finance_book=None, cost_center=None, project=None):
	return _get_filtered_account_balances(
		company, accounts, from_date, to_date, "is_opening='Yes'", finance_book, cost_center, project
	)


def get_account_balances_excluding_opening(company, accounts, from_date, to_date, finance_book=None, cost_center=None, project=None):
	return _get_filtered_account_balances(
		company, accounts, from_date, to_date, "is_opening='No'", finance_book, cost_center, project
	)


def _get_filtered_account_balances(company, accounts, from_date, to_date, opening_condition, finance_book=None, cost_center=None, project=None):
	if not accounts:
		return {}
	conditions = [
		"company=%(company)s", "account IN %(accounts)s", "posting_date BETWEEN %(from_date)s AND %(to_date)s",
		"is_cancelled=0", opening_condition,
	]
	values = {"company": company, "accounts": accounts, "from_date": from_date, "to_date": to_date}
	for fieldname, value in (("finance_book", finance_book), ("cost_center", cost_center), ("project", project)):
		if value:
			conditions.append(f"{fieldname}=%({fieldname})s")
			values[fieldname] = value
	rows = frappe.db.sql(
		f"SELECT account, SUM(debit-credit) balance FROM `tabGL Entry` WHERE {' AND '.join(conditions)} GROUP BY account",
		values, as_dict=True,
	)
	return {row.account: row.balance for row in rows}


def validate_statement_links(company, from_date, to_date, tolerance=None):
	tolerance = flt(
		tolerance if tolerance is not None else frappe.db.get_value("China Finance Settings", company, "reconciliation_tolerance") or 0.01
	)
	try:
		statements = {
			statement_type: build_statement(company, statement_type, from_date, to_date)
			for statement_type in ("Balance Sheet", "Profit and Loss", "Cash Flow", "Changes in Equity")
		}
	except Exception as exc:
		failure = {"passed": False, "difference": 0, "details": _("财务报表无法生成：{0}").format(str(exc))}
		return {key: dict(failure) for key in ("balance_sheet", "profit_equity", "cash_flow")}

	def values(statement_type):
		return {row["row_code"]: flt(row["amount"]) for row in statements[statement_type]["rows"]}

	bs_values, pl_values = values("Balance Sheet"), values("Profit and Loss")
	equity_values, cash_values = values("Changes in Equity"), values("Cash Flow")

	def check(left_values, left_code, right_values, right_code, label):
		missing = [code for code, source in ((left_code, left_values), (right_code, right_values)) if code not in source]
		if missing:
			return {"passed": False, "difference": 0, "details": _("{0}缺少报表行：{1}").format(label, ", ".join(missing))}
		left, right = left_values[left_code], right_values[right_code]
		difference = left - right
		return {
			"passed": abs(difference) <= tolerance, "difference": difference,
			"details": _("{0}：{1} 对 {2}，差额 {3}").format(label, left, right, difference),
		}

	return {
		"balance_sheet": check(bs_values, "TOTAL_ASSETS", bs_values, "TOTAL_LIABILITIES_EQUITY", _("资产负债表平衡")),
		"profit_equity": check(pl_values, "NET_PROFIT", equity_values, "NET_PROFIT", _("净利润与权益变动衔接")),
		"cash_flow": {
			"passed": abs(cash_values.get("CASH_RECONCILIATION_DIFFERENCE", 0)) <= tolerance
			and abs(flt(statements["Cash Flow"]["cash_flow_meta"].get("unclassified_amount"))) <= tolerance,
			"difference": cash_values.get("CASH_RECONCILIATION_DIFFERENCE", 0),
			"details": _("现金流勾稽差额 {0}，未分类现金流 {1}").format(
				cash_values.get("CASH_RECONCILIATION_DIFFERENCE", 0),
				statements["Cash Flow"]["cash_flow_meta"].get("unclassified_amount", 0),
			),
		},
	}


def snapshot_statement(closing_run, statement_type, validation_results=None, notes_payload=None):
	from china_finance.services.cash_equivalent_scope import get_cash_scope_hash

	result = build_statement(closing_run.company, statement_type, closing_run.from_date, closing_run.to_date)
	comparison_from, comparison_to = get_comparison_period(
		closing_run.company, statement_type, closing_run.from_date, closing_run.to_date
	)
	comparison = build_statement(closing_run.company, statement_type, comparison_from, comparison_to)
	comparison_values = {row["row_code"]: row["amount"] for row in comparison["rows"]}
	for row in result["rows"]:
		row["comparison_amount"] = comparison_values.get(row["row_code"], 0)
	result["comparison_from_date"] = str(comparison_from) if comparison_from else None
	result["comparison_to_date"] = str(comparison_to)
	if statement_type == "Changes in Equity":
		result["comparison_equity_matrix"] = comparison.get("equity_matrix")
	result["report_status"] = "正式"
	if validation_results:
		if statement_type == "Balance Sheet":
			result["validation"] = {"balance_sheet": validation_results["balance_sheet"]}
		elif statement_type in ("Profit and Loss", "Changes in Equity"):
			result["validation"] = {"profit_equity": validation_results["profit_equity"]}
		elif statement_type == "Cash Flow":
			result["validation"] = {"cash_flow": validation_results["cash_flow"]}
	if notes_payload:
		result["financial_statement_notes"] = notes_payload
	payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
	template = frappe.get_cached_doc("China Financial Statement Template", result["template"])
	comparison_template = frappe.get_cached_doc("China Financial Statement Template", comparison["template"])
	if statement_type == "Balance Sheet":
		mapping_rows = [
			*get_mappings(closing_run.company, template, closing_run.to_date),
			*get_mappings(closing_run.company, comparison_template, comparison_to),
		]
	else:
		mapping_rows = [
			*get_mapping_revisions(
				closing_run.company, template, closing_run.from_date, closing_run.to_date
			),
			*get_mapping_revisions(
				closing_run.company, comparison_template, comparison_from, comparison_to
			),
		]
	mapping_payload = [dict(row) for row in {row.name: row for row in mapping_rows}.values()]
	mapping_sha256 = hashlib.sha256(
		json.dumps(mapping_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
	).hexdigest()
	existing = frappe.db.get_value(
		"China Report Snapshot", {"closing_run": closing_run.name, "statement_type": statement_type}, "name"
	)
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "China Report Snapshot", "company": closing_run.company,
			"closing_run": closing_run.name, "statement_type": statement_type,
			"template": result["template"], "from_date": closing_run.from_date,
			"template_version": result["template_version"], "report_status": "正式",
			"to_date": closing_run.to_date, "data_json": payload,
			"comparison_from_date": comparison_from, "comparison_to_date": comparison_to,
			"amount_unit": result.get("amount_unit") or "元",
			"approved_by": closing_run.closed_by, "approved_on": closing_run.closed_on,
			"mapping_sha256": mapping_sha256,
			"cash_scope_sha256": get_cash_scope_hash(closing_run.company, closing_run.to_date),
			"validation_json": json.dumps(result.get("validation", {}), ensure_ascii=False, sort_keys=True),
			"notes": notes_payload.get("name") if notes_payload else None,
			"notes_sha256": hashlib.sha256(
				json.dumps(notes_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
			).hexdigest() if notes_payload else None,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
