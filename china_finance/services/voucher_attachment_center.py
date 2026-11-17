import frappe
from frappe import _
from frappe.utils import cint, get_first_day, get_last_day, getdate

from china_finance.services.archive import create_archive_record, verify_archive


READ_ROLES = ("China Archive User", "China Finance Auditor", "Accounts Manager", "China Finance Manager", "System Manager")
WRITE_ROLES = ("China Archive User", "Accounts Manager", "China Finance Manager", "System Manager")


def _check_access(write=False):
	frappe.only_for(WRITE_ROLES if write else READ_ROLES)


def _check_company(company):
	if not company:
		frappe.throw(_("请选择公司"))
	frappe.has_permission("Company", "read", company, throw=True)


def _date_range(filters):
	if filters.get("from_date") or filters.get("to_date"):
		if not filters.get("from_date") or not filters.get("to_date"):
			frappe.throw(_("请同时填写起始日期和截止日期"))
		start, end = getdate(filters.from_date), getdate(filters.to_date)
	else:
		month = filters.get("month") or frappe.utils.nowdate()[:7]
		start, end = get_first_day(f"{month}-01"), get_last_day(f"{month}-01")
	if start > end:
		frappe.throw(_("起始日期不能晚于截止日期"))
	return start, end


@frappe.whitelist()
def get_voucher_attachments(filters=None):
	_check_access()
	filters = frappe._dict(frappe.parse_json(filters) if isinstance(filters, str) else filters or {})
	_check_company(filters.company)
	start, end = _date_range(filters)
	page_length = min(max(cint(filters.get("page_length") or 50), 1), 200)
	start_row = max(cint(filters.get("start") or 0), 0)
	values = {"company": filters.company, "from_date": start, "to_date": end}
	conditions = [
		"d.company=%(company)s", "d.document_category='Accounting Voucher'",
		"d.reference_doctype='China Accounting Voucher'",
		"DATE(d.archived_on) BETWEEN %(from_date)s AND %(to_date)s",
	]
	if not filters.get("include_recycled") and frappe.db.table_exists("China Voucher Recycle Bin Item"):
		conditions.append("NOT EXISTS (SELECT 1 FROM `tabChina Voucher Recycle Bin Item` r WHERE r.voucher=v.name AND r.status='In Recycle Bin')")
	if filters.get("search_text"):
		values["search"] = f"%{filters.search_text.strip()}%"
		conditions.append("(d.file_name LIKE %(search)s OR d.reference_name LIKE %(search)s OR v.statutory_number LIKE %(search)s OR v.remarks LIKE %(search)s)")
	where = " AND ".join(conditions)
	rows = frappe.db.sql(f"""
		SELECT d.name, d.file_name, d.file_size, d.mime_type, d.file, d.reference_name,
			d.archived_on, d.archived_by, d.status, d.sha256, v.statutory_number
		FROM `tabChina Electronic Document` d
		INNER JOIN `tabChina Accounting Voucher` v ON v.name=d.reference_name
		WHERE {where}
		ORDER BY d.archived_on DESC, d.name DESC LIMIT %(start)s, %(page_length)s
	""", {**values, "start": start_row, "page_length": page_length}, as_dict=True)
	stats = frappe.db.sql(f"""SELECT COUNT(*) total_count, COALESCE(SUM(d.file_size), 0) total_size
		FROM `tabChina Electronic Document` d
		INNER JOIN `tabChina Accounting Voucher` v ON v.name=d.reference_name WHERE {where}""", values, as_dict=True)[0]
	return {"rows": rows, "total_count": stats.total_count, "total_size": stats.total_size,
		"from_date": str(start), "to_date": str(end), "page_length": page_length}


@frappe.whitelist()
def archive_voucher_attachment(company, voucher_name, file_url, notes=None):
	_check_access(write=True)
	_check_company(company)
	voucher = frappe.get_doc("China Accounting Voucher", voucher_name)
	voucher.check_permission("read")
	if voucher.company != company:
		frappe.throw(_("关联凭证不属于所选公司"))
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		frappe.throw(_("上传文件不存在"))
	file_doc = frappe.get_doc("File", file_name)
	if not file_doc.is_private:
		frappe.throw(_("凭证附件必须作为私有文件上传"))
	if file_doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("不能归档其他用户上传的文件"), frappe.PermissionError)
	name = create_archive_record(company, "China Accounting Voucher", voucher.name, "Accounting Voucher", file_url)
	if notes:
		frappe.db.set_value("China Electronic Document", name, "notes", notes)
	return {"name": name}


@frappe.whitelist()
def archive_source_voucher_attachment(source_doctype, source_name, file_url, notes=None):
	_check_access(write=True)
	if not source_doctype or not source_name:
		frappe.throw(_("请选择来源凭证"))
	source = frappe.get_doc(source_doctype, source_name)
	source.check_permission("read")
	voucher_name = frappe.db.get_value(
		"China Accounting Voucher",
		{"source_key": f"Posting|{source_doctype}|{source_name}", "docstatus": 1},
		"name",
	)
	if not voucher_name:
		frappe.throw(_("当前凭证尚未生成已提交的中国会计凭证，不能归档附件"))
	voucher = frappe.get_doc("China Accounting Voucher", voucher_name)
	return archive_voucher_attachment(voucher.company, voucher.name, file_url, notes)


@frappe.whitelist()
def verify_voucher_attachment(name):
	_check_access()
	doc = frappe.get_doc("China Electronic Document", name)
	if doc.document_category != "Accounting Voucher" or doc.reference_doctype != "China Accounting Voucher":
		frappe.throw(_("该文件不是凭证附件"))
	return verify_archive(name)
