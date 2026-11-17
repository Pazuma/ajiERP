import csv
import io

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate


SUMMARY_ROLES = ("Accounts User", "Accounts Manager", "China Finance Manager", "China Finance Auditor", "System Manager")


def _dates(filters):

	filters = frappe._dict(filters or {})
	if filters.period_mode == "custom":
		if not filters.from_date or not filters.to_date:
			frappe.throw(_("请填写自定义起始日期和截止日期"))
		start, end = getdate(filters.from_date), getdate(filters.to_date)
	else:
		from_month = filters.from_month or frappe.utils.nowdate()[:7]
		to_month = filters.to_month or from_month
		start = get_first_day(f"{from_month}-01")
		end = get_last_day(f"{to_month}-01")
	if start > end:
		frappe.throw(_("起始日期不能晚于截止日期"))
	return start, end


def _query(filters):
	start, end = _dates(filters)
	values = {"company": filters.company, "from_date": start, "to_date": end}
	where = ["v.company=%(company)s", "v.posting_date BETWEEN %(from_date)s AND %(to_date)s", "v.docstatus=1"]
	if not filters.get("include_recycled") and frappe.db.table_exists("China Voucher Recycle Bin Item"):
		where.append("NOT EXISTS (SELECT 1 FROM `tabChina Voucher Recycle Bin Item` r WHERE r.voucher=v.name AND r.status='In Recycle Bin')")
	if filters.get("search_text"):
		values["search"] = f"%{filters.search_text}%"
		where.append("(v.statutory_number LIKE %(search)s OR v.remarks LIKE %(search)s OR e.remarks LIKE %(search)s OR e.account LIKE %(search)s OR a.account_name LIKE %(search)s OR a.account_number LIKE %(search)s)")
	rows = frappe.db.sql(f"""
		SELECT e.account, COALESCE(a.account_number, '') account_number, a.parent_account,
			COALESCE(a.account_name, e.account) account_name,
			SUM(e.debit) debit, SUM(e.credit) credit,
			COUNT(DISTINCT v.name) voucher_count
		FROM `tabChina Accounting Voucher` v
		INNER JOIN `tabChina Accounting Voucher Entry` e ON e.parent=v.name
		LEFT JOIN `tabAccount` a ON a.name=e.account
		WHERE {' AND '.join(where)}
		GROUP BY e.account, a.account_number, a.account_name, a.parent_account
		ORDER BY a.parent_account, a.account_number, e.account
	""", values, as_dict=True)
	voucher_rows = frappe.db.sql(f"""
		SELECT v.name, v.statutory_number, v.source_doctype, v.source_name, v.posting_date, v.remarks,
			SUM(e.debit) debit, SUM(e.credit) credit
		FROM `tabChina Accounting Voucher` v
		INNER JOIN `tabChina Accounting Voucher Entry` e ON e.parent=v.name
		LEFT JOIN `tabAccount` a ON a.name=e.account
		WHERE {' AND '.join(where)}
		GROUP BY v.name, v.statutory_number, v.source_doctype, v.source_name, v.posting_date, v.remarks
		ORDER BY v.posting_date, v.statutory_number, v.name
	""", values, as_dict=True)
	if filters.get("show_account_category_subtotal"):
		grouped = {}
		for row in rows:
			grouped.setdefault(row.parent_account or _("未分类"), []).append(row)
		with_subtotals = []
		for parent, entries in grouped.items():
			with_subtotals.extend(entries)
			with_subtotals.append(frappe._dict({
				"account": parent, "account_name": _("{0}小计").format(parent),
				"debit": sum(item.debit or 0 for item in entries),
				"credit": sum(item.credit or 0 for item in entries), "is_subtotal": 1,
			}))
		rows = with_subtotals
	stats = frappe.db.sql(f"""SELECT COUNT(*) voucher_count,
		COALESCE(SUM(v.attachment_count),0) attachment_count
		FROM `tabChina Accounting Voucher` v
		WHERE v.name IN (
			SELECT DISTINCT v.name
			FROM `tabChina Accounting Voucher` v
			INNER JOIN `tabChina Accounting Voucher Entry` e ON e.parent=v.name
			LEFT JOIN `tabAccount` a ON a.name=e.account
			WHERE {' AND '.join(where)}
		)""", values, as_dict=True)[0]
	stats.update({"total_debit": sum(row.debit or 0 for row in rows if not row.get("is_subtotal")), "total_credit": sum(row.credit or 0 for row in rows if not row.get("is_subtotal"))})
	return rows, voucher_rows, stats, start, end


@frappe.whitelist()
def get_voucher_summary(filters=None):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else frappe._dict(filters or {})
	frappe.only_for(SUMMARY_ROLES)
	if not filters.company:
		frappe.throw(_("请选择公司"))
	frappe.has_permission("Company", "read", filters.company, throw=True)
	rows, voucher_rows, stats, start, end = _query(filters)
	return {"rows": rows, "voucher_rows": voucher_rows, "totals": stats, "from_date": str(start), "to_date": str(end)}


def _csv_value(value):
	value = str(value if value is not None else "")
	return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@frappe.whitelist()
def export_selected_vouchers(voucher_names=None, filters=None, format="csv"):
	frappe.only_for(SUMMARY_ROLES)
	filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else (filters or {}))
	voucher_names = frappe.parse_json(voucher_names) if isinstance(voucher_names, str) else voucher_names
	if format != "csv":
		frappe.throw(_("仅支持 CSV 导出"))
	if not isinstance(voucher_names, list) or not voucher_names or len(voucher_names) > 500:
		frappe.throw(_("请选择 1 至 500 张凭证"))
	if not all(isinstance(name, str) and name for name in voucher_names) or len(set(voucher_names)) != len(voucher_names):
		frappe.throw(_("凭证编号无效或重复"))
	if not filters.company:
		frappe.throw(_("请选择公司"))
	frappe.has_permission("Company", "read", filters.company, throw=True)

	# Query through the same company/date/search/recycle filters used by the visible list.
	account_rows, voucher_rows, totals, start, end = _query(filters)
	selected = set(voucher_names)
	if not selected.issubset({row.name for row in voucher_rows}):
		frappe.throw(_("所选凭证已不在当前筛选结果中，请刷新后重试"))
	for name in selected:
		frappe.has_permission("China Accounting Voucher", "read", name, throw=True)

	output = io.StringIO(newline="")
	writer = csv.writer(output)
	writer.writerow([_("凭证编号"), _("来源单据"), _("日期"), _("摘要"), _("借方金额"), _("贷方金额")])
	for row in voucher_rows:
		if row.name in selected:
			writer.writerow([_csv_value(row.statutory_number or row.name), _csv_value(row.source_name),
				str(row.posting_date), _csv_value(row.remarks), row.debit or 0, row.credit or 0])
	frappe.response["filename"] = f"selected-vouchers-{start}-{end}.csv"
	frappe.response["filecontent"] = "\ufeff" + output.getvalue()
	frappe.response["type"] = "download"
