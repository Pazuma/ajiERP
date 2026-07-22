import frappe
from frappe import _
from frappe.utils import flt

from china_finance.services.tax_invoice_request import get_invoice_requirement


TOLERANCE = 0.01


def get_output_invoice_rows(company, from_date, to_date):
	rows = frappe.db.sql(
		"""
		SELECT si.name AS sales_invoice, si.company, si.posting_date, si.customer, si.customer_name,
			si.grand_total, si.total_taxes_and_charges, si.outstanding_amount,
			GROUP_CONCAT(DISTINCT request.name ORDER BY request.creation SEPARATOR ', ') AS requests,
			GROUP_CONCAT(DISTINCT request.status ORDER BY request.creation SEPARATOR ', ') AS request_statuses,
			GROUP_CONCAT(DISTINCT tax.name ORDER BY tax.invoice_date SEPARATOR ', ') AS tax_invoices,
			COALESCE(SUM(allocation.allocated_gross_amount), 0) AS allocated_gross_amount,
			COALESCE(SUM(allocation.allocated_tax_amount), 0) AS allocated_tax_amount
		FROM `tabSales Invoice` si
		LEFT JOIN `tabChina Tax Invoice Request Item` request_item ON request_item.sales_invoice=si.name
		LEFT JOIN `tabChina Tax Invoice Request` request ON request.name=request_item.parent AND request.status NOT IN ('Rejected', 'Cancelled')
		LEFT JOIN `tabChina Tax Invoice Allocation` allocation ON allocation.reference_doctype='Sales Invoice' AND allocation.reference_name=si.name
		LEFT JOIN `tabChina Tax Invoice` tax ON tax.name=allocation.parent AND tax.docstatus=1 AND tax.direction='销项'
		WHERE si.company=%s AND si.posting_date BETWEEN %s AND %s AND si.docstatus=1 AND si.is_return=0
		GROUP BY si.name
		ORDER BY si.posting_date, si.name
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	for row in rows:
		row.requirement = get_invoice_requirement(row.company, row.customer, row.posting_date, row.sales_invoice)["requirement"]
	return rows


def evaluate_output_invoice_rows(company, from_date, to_date):
	rows = get_output_invoice_rows(company, from_date, to_date)
	for row in rows:
		issues = []
		if row.requirement == "Required":
			if not row.tax_invoices:
				issues.append(_("未回填税务发票"))
			if abs(flt(row.allocated_gross_amount) - flt(row.grand_total)) > TOLERANCE:
				issues.append(_("价税合计分摊不一致"))
			if abs(flt(row.allocated_tax_amount) - flt(row.total_taxes_and_charges)) > TOLERANCE:
				issues.append(_("税额分摊不一致"))
		row.reconciliation_status = "Blocked" if issues else "Ready"
		row.exception_reason = "；".join(issues)
	return rows


def get_output_tax_gl_check(company, from_date, to_date):
	accounts = frappe.get_all(
		"China Tax Account Mapping",
		filters={"company": company, "direction": "Output", "enabled": 1, "effective_from": ["<=", to_date]},
		or_filters={"effective_to": [">=", from_date], "effective_to": ["is", "not set"]},
		pluck="account",
	)
	tax_amount = frappe.db.sql(
		"""SELECT COALESCE(SUM(tax_amount), 0) FROM `tabChina Tax Invoice`
		WHERE company=%s AND direction='销项' AND docstatus=1 AND invoice_date BETWEEN %s AND %s""",
		(company, from_date, to_date),
	)[0][0]
	if not accounts:
		return {"passed": False, "details": _("未配置销项税科目映射"), "tax_amount": flt(tax_amount), "gl_amount": 0}
	placeholders = ", ".join(["%s"] * len(accounts))
	gl_amount = frappe.db.sql(
		f"""SELECT COALESCE(SUM(credit-debit), 0) FROM `tabGL Entry`
		WHERE company=%s AND posting_date BETWEEN %s AND %s AND is_cancelled=0 AND account IN ({placeholders})""",
		[company, from_date, to_date, *accounts],
	)[0][0]
	return {
		"passed": abs(flt(tax_amount) - flt(gl_amount)) <= TOLERANCE,
		"details": _("税票税额 {0}，总账销项税发生额 {1}").format(flt(tax_amount), flt(gl_amount)),
		"tax_amount": flt(tax_amount), "gl_amount": flt(gl_amount),
	}


def get_output_tax_closing_checks(company, from_date, to_date):
	rows = evaluate_output_invoice_rows(company, from_date, to_date)
	blocked = [row for row in rows if row.reconciliation_status == "Blocked"]
	gl_check = get_output_tax_gl_check(company, from_date, to_date)
	return {
		"coverage": {"passed": not blocked, "count": len(blocked), "details": _("未完成销项票账闭环 {0} 张").format(len(blocked))},
		"gl": gl_check,
	}


def get_input_tax_accounting_check(company, from_date, to_date):
	"""Reconcile allocated input tax to GL by Purchase Invoice accounting period, not tax deduction period."""
	tax_amount = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(allocation.allocated_tax_amount), 0)
		FROM `tabChina Tax Invoice Allocation` allocation
		INNER JOIN `tabChina Tax Invoice` invoice ON invoice.name=allocation.parent
		INNER JOIN `tabPurchase Invoice` purchase_invoice ON purchase_invoice.name=allocation.reference_name
		WHERE allocation.reference_doctype='Purchase Invoice' AND invoice.company=%s
			AND invoice.direction='进项' AND invoice.invoice_status='蓝票' AND invoice.docstatus=1
			AND purchase_invoice.docstatus=1 AND purchase_invoice.posting_date BETWEEN %s AND %s
		""",
		(company, from_date, to_date),
	)[0][0]
	accounts = frappe.get_all(
		"China Tax Account Mapping",
		filters={"company": company, "direction": "Input", "enabled": 1, "effective_from": ["<=", to_date]},
		or_filters={"effective_to": [">=", from_date], "effective_to": ["is", "not set"]},
		pluck="account",
	)
	if not accounts:
		if frappe.db.get_value("China Finance Settings", company, "taxpayer_type") == "小规模纳税人":
			return {"passed": True, "details": _("小规模纳税人不要求配置进项税抵扣科目"), "tax_amount": flt(tax_amount), "gl_amount": 0}
		return {"passed": False, "details": _("未配置进项税科目映射"), "tax_amount": flt(tax_amount), "gl_amount": 0}
	placeholders = ", ".join(["%s"] * len(accounts))
	gl_amount = frappe.db.sql(
		f"""SELECT COALESCE(SUM(debit-credit), 0) FROM `tabGL Entry`
		WHERE company=%s AND posting_date BETWEEN %s AND %s AND is_cancelled=0 AND account IN ({placeholders})""",
		[company, from_date, to_date, *accounts],
	)[0][0]
	return {
		"passed": abs(flt(tax_amount) - flt(gl_amount)) <= TOLERANCE,
		"details": _("已分摊进项税额 {0}，总账进项税发生额 {1}").format(flt(tax_amount), flt(gl_amount)),
		"tax_amount": flt(tax_amount), "gl_amount": flt(gl_amount),
	}


def get_input_tax_pending_check(company, to_date):
	row = frappe.db.sql(
		"""SELECT COUNT(*), COALESCE(SUM(tax_amount), 0) FROM `tabChina Tax Invoice`
		WHERE company=%s AND direction='进项' AND invoice_status='蓝票' AND docstatus=1
			AND invoice_date<=%s AND deduction_status='已勾选'""",
		(company, to_date),
	)[0]
	return {"passed": True, "count": row[0], "details": _("已勾选未抵扣 {0} 张，税额 {1}").format(row[0], flt(row[1]))}


def get_input_tax_closing_checks(company, from_date, to_date):
	return {"accounting": get_input_tax_accounting_check(company, from_date, to_date), "pending": get_input_tax_pending_check(company, to_date)}


@frappe.whitelist()
def preview_output_tax_checks(company, from_date, to_date):
	frappe.only_for(("System Manager", "China Finance Manager", "China Tax User", "China Finance Auditor"))
	return get_output_tax_closing_checks(company, from_date, to_date)


@frappe.whitelist()
def preview_input_tax_checks(company, from_date, to_date):
	frappe.only_for(("System Manager", "China Finance Manager", "China Tax User", "China Finance Auditor"))
	return get_input_tax_closing_checks(company, from_date, to_date)
