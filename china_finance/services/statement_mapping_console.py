import frappe
from frappe import _
from frappe.utils import cint, getdate, today

from china_finance.services.financial_statement import get_template
from china_finance.services.statement_mapping_review import REVIEW_ROLES, set_mapping_reviewed
from china_finance.setup.templates import TEMPLATE_EFFECTIVE_FROM, classify_company_account, refine_classification_for_template

READ_ROLES = (
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"China Finance Manager",
	"China Finance Auditor",
)
WRITE_ROLES = REVIEW_ROLES
TEMPLATE_WRITE_ROLES = ("System Manager", "China Finance Manager")
STATEMENT_TYPES = ("Balance Sheet", "Profit and Loss", "Cash Flow", "Changes in Equity")


def _require_read_access():
	frappe.only_for(READ_ROLES)


def _require_write_access():
	frappe.only_for(WRITE_ROLES)


def _require_template_write_access():
	frappe.only_for(TEMPLATE_WRITE_ROLES)


@frappe.whitelist()
def get_mapping_console(company, statement_type, accounting_standard=None):
	"""Aggregate the statement template rows, mappings and unmapped accounts for the console."""
	_require_read_access()
	if statement_type not in STATEMENT_TYPES:
		frappe.throw(_("未知的报表类型 {0}").format(statement_type))
	if accounting_standard not in ("企业会计准则", "小企业会计准则"):
		accounting_standard = None
	settings = frappe.get_cached_doc("China Finance Settings", company)
	report_effective_from = settings.statutory_reporting_activation_date or settings.activation_date
	mapping_effective_from = settings.statement_mapping_activation_date or report_effective_from or TEMPLATE_EFFECTIVE_FROM
	template = get_template(company, statement_type, today(), accounting_standard=accounting_standard)
	report_effective_from = template.effective_from or report_effective_from
	mappings = frappe.get_all(
		"China Financial Statement Mapping",
		filters={"company": company, "template": template.name},
		fields=[
			"name", "account", "row_code", "cash_inflow_row_code", "cash_outflow_row_code",
			"supplementary_row_code", "mapping_basis", "sign_multiplier", "mapping_source", "reviewed", "effective_from", "effective_to",
		],
		order_by="account",
	)
	leaf_accounts = frappe.get_all(
		"Account",
		filters={"company": company, "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "account_number", "root_type", "account_type"],
		order_by="name",
	)
	all_accounts = frappe.get_all(
		"Account",
		filters={"company": company, "disabled": 0},
		fields=["name", "account_name", "account_number", "parent_account", "is_group", "root_type"],
		order_by="lft",
	)
	payload = build_console_payload(template, mappings, leaf_accounts, all_accounts, company=company)
	payload["configuration"] = {
		"report_effective_from": str(report_effective_from or ""),
		"mapping_effective_from": str(mapping_effective_from or ""),
	}
	return payload


def build_console_payload(template, mappings, leaf_accounts, all_accounts=None, company=None):
	"""Pure aggregation so tests can run without a database."""
	account_index = {account.name: account for account in leaf_accounts}
	row_mappings = {}
	mapped_accounts = set()
	pending_review = 0
	for mapping in mappings:
		account = account_index.get(mapping.account)
		item = {
			"name": mapping.name,
			"account": mapping.account,
			"account_name": account.account_name if account else mapping.account,
			"account_number": account.account_number if account else None,
			"root_type": account.root_type if account else None,
			"row_code": mapping.row_code,
			"supplementary_row_code": getattr(mapping, "supplementary_row_code", None),
			"mapping_basis": getattr(mapping, "mapping_basis", None),
			"cash_inflow_row_code": mapping.cash_inflow_row_code,
			"cash_outflow_row_code": mapping.cash_outflow_row_code,
			"sign_multiplier": -1 if cint(mapping.sign_multiplier) == -1 else 1,
			"mapping_source": mapping.mapping_source,
			"reviewed": bool(mapping.reviewed),
			"effective_from": str(mapping.effective_from or ""),
			"effective_to": str(mapping.effective_to or ""),
		}
		row_mappings.setdefault(mapping.row_code, []).append(item)
		mapped_accounts.add(mapping.account)
		pending_review += 0 if mapping.reviewed else 1
	rows = [
		{
			"row_code": row.row_code,
			"label": row.label,
			"row_type": row.row_type,
			"indent": int(bool(row.indent)),
			"bold": int(bool(row.bold)),
			"formula": row.formula,
			"balance_direction": row.balance_direction,
			"mappings": row_mappings.get(row.row_code, []),
		}
		for row in template.rows
	]
	root_order = {"Asset": 0, "Liability": 1, "Equity": 2, "Income": 3, "Expense": 4}
	valid_rows = {row.row_code: row.row_type for row in template.rows}
	row_labels = {row.row_code: row.label for row in template.rows}
	unmapped_accounts = [account for account in leaf_accounts if account.name not in mapped_accounts]
	likely_row_by_account = {}
	for account in unmapped_accounts:
		classification, _basis = classify_company_account(company, account, template.statement_type) if company else (None, None)
		classification = refine_classification_for_template(account, template.statement_type, valid_rows, classification)
		account.likely_row_code = classification[0] if isinstance(classification, tuple) else classification
		if account.likely_row_code in row_labels:
			likely_row_by_account[account.name] = {
				"row_code": account.likely_row_code,
				"label": row_labels[account.likely_row_code],
			}
	unmapped_accounts.sort(key=lambda account: (root_order.get(account.root_type, 99), account.account_number or "", account.name))
	accounts = [
		{
			"name": account.name,
			"account_name": account.account_name,
			"account_number": account.account_number,
			"parent_account": account.parent_account or "",
			"is_group": int(bool(account.is_group)),
			"root_type": account.root_type,
			"likely_row": likely_row_by_account.get(account.name),
		}
		for account in (all_accounts or [])
	]
	return {
		"template": {
			"name": template.name,
			"version": template.version,
			"accounting_standard": template.accounting_standard,
			"statement_type": template.statement_type,
		},
		"rows": rows,
		"accounts": accounts,
		"unmapped_accounts": unmapped_accounts,
		"summary": {
			"total_leaf_accounts": len(leaf_accounts),
			"mapped_accounts": len(mapped_accounts),
			"unmapped_accounts": len(unmapped_accounts),
			"total_mappings": len(mappings),
			"pending_review": pending_review,
		},
	}


@frappe.whitelist()
def save_mapping(company, template, account, row_code, cash_inflow_row_code=None, cash_outflow_row_code=None, sign_multiplier=1):
	"""Create or update the mapping of one account to a statement row; DocType validates."""
	_require_write_access()
	effective_from = _default_effective_from(company)
	mapping_key = "|".join((company, template, account, effective_from))
	values = {
		"row_code": row_code,
		"cash_inflow_row_code": cash_inflow_row_code or None,
		"cash_outflow_row_code": cash_outflow_row_code or None,
		"sign_multiplier": "-1" if cint(sign_multiplier) == -1 else "1",
	}
	doc = frappe.get_doc(
			{
				"doctype": "China Financial Statement Mapping",
				"company": company,
				"template": template,
				"account": account,
				"mapping_key": mapping_key,
				"effective_from": effective_from,
				"mapping_source": "Manual",
			}
	)
	doc.update(values)
	doc.save()
	return {"name": doc.name, "row_code": doc.row_code, "reviewed": bool(doc.reviewed)}


def _default_effective_from(company):
	settings = frappe.get_cached_doc("China Finance Settings", company)
	return settings.statement_mapping_activation_date or settings.statutory_reporting_activation_date or settings.activation_date or TEMPLATE_EFFECTIVE_FROM


@frappe.whitelist()
def save_mapping_configuration(company, template=None, report_effective_from=None, mapping_effective_from=None):
	"""Save the company-level dates used by reports and new statement mappings."""
	_require_template_write_access()
	settings = frappe.get_doc("China Finance Settings", company)
	report_effective_from = getdate(report_effective_from) if report_effective_from else None
	mapping_effective_from = getdate(mapping_effective_from) if mapping_effective_from else None
	if report_effective_from and getdate(settings.activation_date) > report_effective_from:
		frappe.throw(_("报表生效日期不能早于中国财务启用日期"))
	if mapping_effective_from and getdate(settings.activation_date) > mapping_effective_from:
		frappe.throw(_("科目映射统一生效日期不能早于中国财务启用日期"))
	settings.statutory_reporting_activation_date = report_effective_from
	settings.statement_mapping_activation_date = mapping_effective_from
	settings.save()
	if template and report_effective_from:
		template_doc = frappe.get_doc("China Financial Statement Template", template)
		template_doc.effective_from = report_effective_from
		template_doc.save()
	frappe.clear_cache(doctype="China Finance Settings")
	return {
		"report_effective_from": str(report_effective_from or ""),
		"mapping_effective_from": str(mapping_effective_from or ""),
	}


@frappe.whitelist()
def remove_mapping(name):
	_require_write_access()
	doc = frappe.get_doc("China Financial Statement Mapping", name)
	if not doc.has_permission("delete"):
		frappe.throw(_("无权删除该财务报表科目映射"), frappe.PermissionError)
	doc.delete()
	return {"deleted": name}


@frappe.whitelist()
def set_mappings_reviewed(names, reviewed=1):
	"""Bulk review/unreview through the existing single-mapping review API."""
	_require_write_access()
	if isinstance(names, str):
		names = frappe.parse_json(names)
	updated = [set_mapping_reviewed(name, reviewed=reviewed) for name in names]
	return {"updated": len(updated)}


@frappe.whitelist()
def save_template_formula(template, row_code, formula):
	"""Edit one Formula row of a statement template; DocType validation checks the formula."""
	_require_template_write_access()
	doc = frappe.get_doc("China Financial Statement Template", template)
	if not doc.has_permission("write"):
		frappe.throw(_("无权编辑该报表模板"), frappe.PermissionError)
	return update_template_formula(doc, row_code, formula)


def update_template_formula(template_doc, row_code, formula):
	row = next((row for row in template_doc.rows if row.row_code == row_code), None)
	if not row:
		frappe.throw(_("模板中不存在报表行 {0}").format(row_code))
	if row.row_type != "Formula":
		frappe.throw(_("报表行 {0} 不是公式行，不能编辑公式").format(row_code))
	row.formula = (formula or "").strip()
	# validate() on the template checks every Formula row via validate_formula.
	template_doc.save()
	return {"template": template_doc.name, "row_code": row.row_code, "formula": row.formula}
