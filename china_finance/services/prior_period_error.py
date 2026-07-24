from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate


APPROVERS = ("System Manager", "China Finance Manager")


def _require_company_read(company):
	frappe.has_permission("Company", "read", company, throw=True)


@frappe.whitelist()
def preview_prior_period_error_adjustment(company, journal_entry, prior_period_end):
	"""Preview the restatement before creating an auditable adjustment record."""
	_require_company_read(company)
	return build_adjustment_lines(company, journal_entry, prior_period_end)


@frappe.whitelist()
def create_prior_period_error_adjustment(company, journal_entry, prior_period_end, reason, evidence_file):
	frappe.only_for(APPROVERS)
	_require_company_read(company)
	doc = frappe.get_doc({
		"doctype": "China Prior Period Error Adjustment",
		"company": company,
		"journal_entry": journal_entry,
		"prior_period_end": getdate(prior_period_end),
		"reason": reason,
		"evidence_file": evidence_file,
	}).insert()
	return {"name": doc.name, "status": doc.status, "lines": doc.lines}


@frappe.whitelist()
def submit_prior_period_error_adjustment(name):
	frappe.only_for(APPROVERS)
	doc = frappe.get_doc("China Prior Period Error Adjustment", name)
	_require_company_read(doc.company)
	doc.submit()
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


@frappe.whitelist()
def cancel_prior_period_error_adjustment(name):
	frappe.only_for(APPROVERS)
	doc = frappe.get_doc("China Prior Period Error Adjustment", name)
	_require_company_read(doc.company)
	doc.cancel()
	return {"name": doc.name, "status": doc.status, "docstatus": doc.docstatus}


@frappe.whitelist()
def get_prior_period_error_adjustments(company, from_date=None, to_date=None):
	_require_company_read(company)
	filters = {"company": company}
	if from_date and to_date:
		filters["prior_period_end"] = ["between", [getdate(from_date), getdate(to_date)]]
	return frappe.get_all(
		"China Prior Period Error Adjustment", filters=filters,
		fields=["name", "journal_entry", "prior_period_end", "status", "docstatus", "approved_by", "approved_on"],
		order_by="prior_period_end desc, creation desc",
	)


def build_adjustment_lines(company, journal_entry, prior_period_end):
	"""Derive restatement effects from the approved corrective Journal Entry."""
	from china_finance.services.financial_statement import (
		classify_equity_component, get_mapping_direction, get_mappings, get_template,
	)

	template = get_template(company, "Balance Sheet", prior_period_end)
	mappings = {row.account: row for row in get_mappings(company, template, prior_period_end)}
	rows = frappe.db.sql(
		"""SELECT account, SUM(debit-credit) AS balance FROM `tabGL Entry`
		WHERE company=%(company)s AND voucher_type='Journal Entry' AND voucher_no=%(voucher_no)s
		AND is_cancelled=0 GROUP BY account HAVING ABS(SUM(debit-credit)) > 0.005""",
		{"company": company, "voucher_no": journal_entry}, as_dict=True,
	)
	retained = frappe.db.get_value("China Finance Settings", company, "retained_earnings_account")
	lines = []
	for row in rows:
		mapping = mappings.get(row.account)
		if row.account == retained:
			lines.append({
				"account": row.account, "statement_type": "Changes in Equity", "row_code": "ERROR_CORRECTION",
				"amount": -flt(row.balance), "equity_component": "retained_earnings",
			})
			continue
		if not mapping:
			frappe.throw(_("追溯调整科目 {0} 未配置资产负债表映射").format(row.account))
		amount = flt(row.balance) * int(mapping.sign_multiplier)
		if get_mapping_direction(template, mapping.row_code) == "Credit Positive":
			amount = -amount
		lines.append({
			"account": row.account, "statement_type": "Balance Sheet", "row_code": mapping.row_code,
			"amount": amount, "equity_component": classify_equity_component(row.account),
		})
	return lines


def get_restatement_values(company, statement_type, prior_period_end):
	"""Return approved strict-restatement amounts for one comparative period."""
	values = defaultdict(float)
	for adjustment in frappe.get_all(
		"China Prior Period Error Adjustment",
		filters={"company": company, "prior_period_end": getdate(prior_period_end), "docstatus": 1, "status": "已审批"},
		pluck="name",
	):
		for line in frappe.get_all(
			"China Prior Period Error Adjustment Line",
			filters={"parent": adjustment, "parenttype": "China Prior Period Error Adjustment", "statement_type": statement_type},
			fields=["row_code", "amount", "equity_component"],
		):
			values[line.row_code] += flt(line.amount)
	return dict(values)


def get_prior_period_error_readiness(company, from_date, to_date):
	rows = frappe.get_all(
		"China Prior Period Error Adjustment", filters={"company": company, "prior_period_end": ["<=", to_date]},
		fields=["name", "docstatus", "status", "evidence_file", "journal_entry"],
	)
	pending = [row.name for row in rows if row.docstatus != 1 or row.status != "已审批" or not row.evidence_file]
	return {
		"passed": not pending,
		"count": len(pending),
		"approved_count": sum(row.docstatus == 1 and row.status == "已审批" for row in rows),
		"details": _("待完成前期差错更正 {0} 条").format(len(pending)) if pending else _("前期差错更正已复核"),
	}
