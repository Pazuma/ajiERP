import frappe
from frappe import _

from erpnext.accounts.report.general_ledger import general_ledger


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	standard_filters = frappe._dict(
		company=filters.company,
		finance_book=filters.get("finance_book"),
		from_date=filters.from_date,
		to_date=filters.to_date,
		account=filters.get("account") or [],
		voucher_no=filters.get("voucher_no"),
		categorize_by="",
		include_default_book_entries=0 if filters.get("finance_book") else 1,
		show_remarks=1,
	)
	_standard_columns, rows = general_ledger.execute(standard_filters)
	opening = _find_summary_row(rows, _("Opening"))
	rows = [row for row in rows if row.get("posting_date")]
	if filters.get("keyword"):
		needle = filters.keyword.lower()
		rows = [row for row in rows if needle in _search_text(row)]
	return get_columns(), build_rows(opening, rows, filters)


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is mandatory"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory"))
	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))
	if (frappe.utils.getdate(filters.to_date) - frappe.utils.getdate(filters.from_date)).days > 366:
		frappe.throw(_("Date range cannot exceed 366 days"))


def _find_summary_row(rows, label):
	return next((row for row in rows if row.get("account") == label), frappe._dict())


def _search_text(row):
	return " ".join(str(row.get(key) or "") for key in ("remarks", "voucher_no", "party_name", "party")).lower()


def build_rows(opening, rows, filters):
	opening_balance = opening.get("balance") or 0
	balance = opening_balance
	result = [{"row_kind": "opening", "remarks": _("本月期初"), "balance": opening_balance}]
	for row in rows:
		row = frappe._dict(row)
		balance += (row.get("debit") or 0) - (row.get("credit") or 0)
		row.balance = balance
		row.row_kind = "detail"
		result.append(row)
	if rows and filters.get("show_daily_subtotal"):
		detail_rows = result[1:]
		result = result[:1]
		current_date = None
		day_rows = []
		for row in detail_rows:
			posting_date = row.get("posting_date")
			if current_date is not None and posting_date != current_date:
				result.extend(day_rows)
				result.append(_daily_subtotal(current_date, day_rows))
				day_rows = []
			current_date = posting_date
			day_rows.append(row)
		result.extend(day_rows)
		result.append(_daily_subtotal(current_date, day_rows))
	period_debit = sum(row.get("debit") or 0 for row in rows)
	period_credit = sum(row.get("credit") or 0 for row in rows)
	result.append({
		"row_kind": "summary",
		"remarks": _("本期小计"),
		"debit": period_debit,
		"credit": period_credit,
		"balance": balance,
	})
	result.append({"row_kind": "closing", "remarks": _("本月期末"), "balance": balance})
	return result


def _daily_subtotal(posting_date, rows):
	return {
		"row_kind": "summary",
		"posting_date": posting_date,
		"remarks": _("本日小计"),
		"debit": sum(row.get("debit") or 0 for row in rows),
		"credit": sum(row.get("credit") or 0 for row in rows),
	}


def get_columns():
	return [
		{"label": _("日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("凭证类型"), "fieldname": "voucher_type", "hidden": 1},
		{"label": _("凭证"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 140},
		{"label": _("摘要"), "fieldname": "remarks", "fieldtype": "Data", "width": 240},
		{"label": _("科目"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("往来单位"), "fieldname": "party_name", "fieldtype": "Data", "width": 140},
		{"label": _("收入（借方）"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("支出（贷方）"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("余额"), "fieldname": "balance", "fieldtype": "Currency", "width": 120},
		{"label": _("备注"), "fieldname": "against", "fieldtype": "Data", "width": 180},
	]
