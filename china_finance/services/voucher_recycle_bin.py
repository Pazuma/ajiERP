import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

READ_ROLES = ("Accounts User", "Accounts Manager", "China Finance Manager", "System Manager")
WRITE_ROLES = ("Accounts Manager", "China Finance Manager", "System Manager")


def _access(write=False):
	frappe.only_for(WRITE_ROLES if write else READ_ROLES)


def _company(company):
	if not company:
		frappe.throw(_("请选择公司"))
	frappe.has_permission("Company", "read", company, throw=True)


def _names(value):
	if isinstance(value, str):
		value = frappe.parse_json(value)
	return list(dict.fromkeys(value or []))


@frappe.whitelist()
def list_recycle_bin(filters=None, start=0, page_length=50):
	_access()
	filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters or {})
	_company(filters.company)
	start_date = getdate(filters.get("from_date") or f"{nowdate()[:7]}-01")
	end_date = getdate(filters.get("to_date") or nowdate())
	values = {"company": filters.company, "start_date": start_date, "end_date": end_date,
		"start": max(cint(start), 0), "page_length": min(max(cint(page_length), 1), 200)}
	where = ["r.company=%(company)s", "r.status='In Recycle Bin'", "r.posting_date BETWEEN %(start_date)s AND %(end_date)s"]
	if filters.get("search_text"):
		values["search"] = f"%{filters.search_text.strip()}%"
		where.append("(r.statutory_number LIKE %(search)s OR r.voucher LIKE %(search)s OR r.deleted_by LIKE %(search)s)")
	where_sql = " AND ".join(where)
	rows = frappe.db.sql(f"""SELECT r.name, r.voucher, r.posting_date, r.statutory_number,
		r.deleted_by, r.deleted_at FROM `tabChina Voucher Recycle Bin Item` r
		WHERE {where_sql} ORDER BY r.deleted_at DESC, r.name DESC
		LIMIT %(start)s, %(page_length)s""", values, as_dict=True)
	total = frappe.db.sql(f"SELECT COUNT(*) total FROM `tabChina Voucher Recycle Bin Item` r WHERE {where_sql}", values, as_dict=True)[0].total
	return {"rows": rows, "total_count": total, "from_date": str(start_date), "to_date": str(end_date), "page_length": values["page_length"]}


@frappe.whitelist()
def move_to_recycle_bin(voucher_names):
	_access(write=True)
	created = []
	for name in _names(voucher_names):
		voucher = frappe.get_doc("China Accounting Voucher", name)
		voucher.check_permission("read")
		if frappe.db.exists("China Voucher Recycle Bin Item", {"voucher": name, "status": "In Recycle Bin"}):
			continue
		item = frappe.get_doc({"doctype": "China Voucher Recycle Bin Item", "company": voucher.company, "voucher": voucher.name,
			"posting_date": voucher.posting_date, "statutory_number": voucher.statutory_number, "deleted_by": frappe.session.user,
			"deleted_at": now_datetime(), "snapshot_json": json.dumps({"remarks": voucher.remarks, "total_debit": voucher.total_debit, "total_credit": voucher.total_credit}, default=str)})
		item.insert(ignore_permissions=True)
		created.append(item.name)
	return {"names": created, "count": len(created)}


@frappe.whitelist()
def restore_from_recycle_bin(item_names):
	_access(write=True)
	restored = []
	for name in _names(item_names):
		item = frappe.get_doc("China Voucher Recycle Bin Item", name)
		_company(item.company)
		if item.status != "In Recycle Bin":
			continue
		item.db_set({"status": "Restored", "restored_by": frappe.session.user, "restored_at": now_datetime()})
		restored.append(item.voucher)
	return {"vouchers": restored, "count": len(restored)}


@frappe.whitelist()
def purge_recycle_bin(item_names):
	_access(write=True)
	if "System Manager" not in frappe.get_roles() and "China Finance Manager" not in frappe.get_roles():
		frappe.throw(_("无权彻底删除回收站记录"), frappe.PermissionError)
	count = 0
	for name in _names(item_names):
		item = frappe.get_doc("China Voucher Recycle Bin Item", name)
		item.db_set({"status": "Purged", "purged_by": frappe.session.user, "purged_at": now_datetime()})
		count += 1
	return {"count": count}


def purge_expired_recycle_bin():
	cutoff = add_days(nowdate(), -15)
	rows = frappe.get_all("China Voucher Recycle Bin Item", filters={"status": "In Recycle Bin", "deleted_at": ["<", cutoff]}, pluck="name")
	for name in rows:
		frappe.db.set_value("China Voucher Recycle Bin Item", name, {"status": "Purged", "purged_by": "Administrator", "purged_at": now_datetime()})
	frappe.db.commit()
