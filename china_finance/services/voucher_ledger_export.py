"""Selected-voucher export for the China Voucher Ledger report."""

import csv
import io

import frappe
from frappe import _


REPORT_ROLES = ("Accounts Manager", "Accounts User", "China Finance Auditor", "System Manager")


def _safe_csv_value(value):
	if value is None:
		return ""
	if isinstance(value, (int, float)):
		return value
	text = str(value)
	return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@frappe.whitelist()
def download_selected_vouchers(voucher_names, filters):
	frappe.only_for(REPORT_ROLES)
	voucher_names = frappe.parse_json(voucher_names) if isinstance(voucher_names, str) else voucher_names
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if not isinstance(voucher_names, list) or not voucher_names or len(voucher_names) > 500:
		frappe.throw(_("请勾选 1 至 500 张凭证。"))
	if any(not isinstance(name, str) or not name for name in voucher_names) or len(set(voucher_names)) != len(voucher_names):
		frappe.throw(_("凭证选择无效或重复。"))
	if not filters.get("company"):
		frappe.throw(_("请选择公司。"))
	frappe.has_permission("Company", "read", filters["company"], throw=True)

	from china_finance.china_finance.report.china_voucher_ledger.china_voucher_ledger import execute

	columns, rows = execute(filters)
	selected = set(voucher_names)
	visible = {row.get("voucher_snapshot") for row in rows if row.get("indent") == 0}
	if not selected.issubset(visible):
		frappe.throw(_("部分所选凭证已不在当前筛选结果中，请刷新后重试。"))
	for name in selected:
		frappe.has_permission("China Accounting Voucher", "read", name, throw=True)

	columns = [column for column in columns if column.get("fieldname") != "_select_voucher"]
	output = io.StringIO(newline="")
	writer = csv.writer(output)
	writer.writerow([column.get("label") for column in columns])
	for row in rows:
		if row.get("voucher_snapshot") not in selected:
			continue
		writer.writerow([_safe_csv_value(row.get(column.get("fieldname"))) for column in columns])

	frappe.response["filename"] = "查凭证-选中项.csv"
	frappe.response["filecontent"] = "\ufeff" + output.getvalue()
	frappe.response["type"] = "download"
