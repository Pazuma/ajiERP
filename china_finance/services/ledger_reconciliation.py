import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_ar_ap_ledger_rows(company, to_date, account=None, party_type=None, party=None, tolerance=None):
	from erpnext.accounts.report.general_and_payment_ledger_comparison.general_and_payment_ledger_comparison import execute

	tolerance = flt(
		tolerance if tolerance is not None else frappe.db.get_value("China Finance Settings", company, "reconciliation_tolerance") or 0.01
	)
	if isinstance(account, str):
		account = [account]
	filters = frappe._dict(
		company=company, period_start_date=None, period_end_date=getdate(to_date), account=account,
		party_type=party_type, party=party, voucher_no=None,
	)
	_columns, rows = execute(filters)
	result = []
	for row in rows:
		row = frappe._dict(row)
		row.gl_balance = flt(row.gl_balance)
		row.pl_balance = flt(row.pl_balance)
		row.difference = row.gl_balance - row.pl_balance
		row.reconciliation_status = "Blocked" if abs(row.difference) > tolerance else "Ready"
		result.append(row)
	return result


def get_ar_ap_ledger_check(company, to_date):
	rows = get_ar_ap_ledger_rows(company, to_date)
	blocked = [row for row in rows if row.reconciliation_status == "Blocked"]
	total_difference = sum(abs(flt(row.difference)) for row in blocked)
	return {
		"passed": not blocked, "count": len(blocked), "difference": total_difference, "rows": blocked,
		"details": _("总账与付款台账差异 {0} 项，差额绝对值合计 {1}").format(len(blocked), flt(total_difference)),
	}


@frappe.whitelist()
def preview_ar_ap_ledger_check(company, to_date):
	frappe.only_for(("System Manager", "Accounts Manager", "China Finance Manager", "China Finance Auditor"))
	return get_ar_ap_ledger_check(company, getdate(to_date))
