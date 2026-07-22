import frappe
from frappe import _
from frappe.utils import getdate

from china_finance.services.closing import count_voucher_hash_errors


def execute(filters=None):
	filters = frappe._dict(filters or {})
	activation_date = frappe.db.get_value(
		"China Finance Settings", {"company": filters.company, "enabled": 1}, "activation_date"
	)
	if activation_date and getdate(activation_date) > getdate(filters.from_date):
		filters.from_date = activation_date
	data = []
	missing = frappe.db.sql(
		"""
		SELECT gle.voucher_type AS source_doctype, gle.voucher_no AS source_name,
			MIN(gle.posting_date) AS posting_date, 'Missing Voucher' AS issue
		FROM `tabGL Entry` gle
		LEFT JOIN `tabChina Accounting Voucher` cav
			ON cav.source_key=CONCAT('Posting|', gle.voucher_type, '|', gle.voucher_no) AND cav.docstatus=1
		WHERE gle.company=%(company)s AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND gle.is_cancelled=0 AND cav.name IS NULL
		GROUP BY gle.voucher_type, gle.voucher_no
		""",
		filters,
		as_dict=True,
	)
	data.extend(missing)
	for issue in frappe.get_all(
		"China Voucher Sync Issue",
		filters={
			"company": filters.company,
			"posting_date": ["between", [filters.from_date, filters.to_date]],
			"status": "Pending",
		},
		fields=["posting_date", "source_doctype", "source_name", "last_error"],
	):
		data.append(
			{
				"posting_date": issue.posting_date,
				"source_doctype": issue.source_doctype,
				"source_name": issue.source_name,
				"issue": _("冲销审计快照待补齐：{0}").format(issue.last_error or _("等待重试")),
			}
		)
	for name in frappe.get_all(
		"China Accounting Voucher",
		filters={"company": filters.company, "posting_date": ["between", [filters.from_date, filters.to_date]], "docstatus": 1},
		pluck="name",
	):
		doc = frappe.get_doc("China Accounting Voucher", name)
		from china_finance.services.voucher import calculate_entries_hash

		if calculate_entries_hash(doc.entries) != doc.source_hash:
			data.append({"posting_date": doc.posting_date, "statutory_number": doc.statutory_number, "source_doctype": doc.source_doctype, "source_name": doc.source_name, "issue": "Hash Mismatch"})
	message = _("共发现 {0} 个异常").format(len(data))
	return get_columns(), data, message


def get_columns():
	return [
		{"label": _("日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("凭证号"), "fieldname": "statutory_number", "fieldtype": "Data", "width": 150},
		{"label": _("来源类型"), "fieldname": "source_doctype", "fieldtype": "Link", "options": "DocType", "width": 140},
		{"label": _("来源单据"), "fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 170},
		{"label": _("异常"), "fieldname": "issue", "fieldtype": "Data", "width": 180},
	]
