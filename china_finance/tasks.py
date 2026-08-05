import frappe

from china_finance.services.voucher import backfill_enabled_company_vouchers


def backfill_voucher_snapshots():
	"""Gradually backfill historical snapshots for every enabled company."""
	if not frappe.db.exists("DocType", "China Finance Settings"):
		return
	for company in frappe.get_all("China Finance Settings", filters={"enabled": 1}, pluck="company"):
		try:
			backfill_enabled_company_vouchers(company)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"China Finance voucher backfill failed: {company}")
