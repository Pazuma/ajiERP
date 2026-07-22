import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = ["v.company=%(company)s", "v.posting_date BETWEEN %(from_date)s AND %(to_date)s", "v.docstatus=1"]
	for fieldname, column in (("voucher_word", "v.voucher_word"), ("account", "e.account"), ("party_type", "e.party_type"), ("party", "e.party")):
		if filters.get(fieldname):
			conditions.append(f"{column}=%({fieldname})s")
	data = frappe.db.sql(
		f"""
		SELECT v.posting_date, v.statutory_number, v.voucher_word, v.source_doctype, v.source_name,
			e.account, e.party_type, e.party, e.cost_center, e.project, e.remarks, e.debit, e.credit
		FROM `tabChina Accounting Voucher` v
		INNER JOIN `tabChina Accounting Voucher Entry` e ON e.parent=v.name
		WHERE {' AND '.join(conditions)}
		ORDER BY v.posting_date, v.sequence_number, e.idx
		""",
		filters,
		as_dict=True,
	)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("凭证日期"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("法定凭证号"), "fieldname": "statutory_number", "fieldtype": "Data", "width": 150},
		{"label": _("来源类型"), "fieldname": "source_doctype", "fieldtype": "Link", "options": "DocType", "width": 130},
		{"label": _("来源单据"), "fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 150},
		{"label": _("科目"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 220},
		{"label": _("往来类型"), "fieldname": "party_type", "fieldtype": "Data", "width": 100},
		{"label": _("往来单位"), "fieldname": "party", "fieldtype": "Dynamic Link", "options": "party_type", "width": 150},
		{"label": _("摘要"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
		{"label": _("借方"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("贷方"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
	]
