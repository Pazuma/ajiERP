import frappe
from frappe.utils import now_datetime

SOURCE_FIELDS = {
	"Work Order": "custom_auto_fulfilment",
	"Delivery Note": "custom_auto_fulfilment",
	"China Sales Settlement": "auto_reconciliation_statement",
	"Purchase Follow Up": "auto_reconciliation_statement",
}
COUNT_KEYS = {"Delivery Note": "delivery_note", "Work Order": "work_order",
	"China Sales Settlement": "china_sales_settlement", "Purchase Follow Up": "purchase_follow_up"}
ALLOWED_DOCTYPES = set(SOURCE_FIELDS)


def _visible_names(doctype, names=None):
	field = SOURCE_FIELDS[doctype]
	if not frappe.get_meta(doctype).has_field(field) or not frappe.has_permission(doctype, "read"):
		return []
	filters = {"docstatus": 0, field: ["is", "set"] if field != "custom_auto_fulfilment" else 1}
	if doctype in ("China Sales Settlement", "Purchase Follow Up"):
		started_at = frappe.db.get_single_value("System Settings", "auto_draft_finance_enabled_at")
		if not started_at:
			return []
		filters["creation"] = [">=", started_at]
	if names is not None:
		if not names:
			return []
		filters["name"] = ["in", names]
	# get_list applies user permissions; get_all does not.
	return frappe.get_list(doctype, filters=filters, pluck="name", limit_page_length=0)


def _validate_target(doctype, name):
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw("不支持的自动草稿类型")
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	if doc.docstatus != 0 or not doc.get(SOURCE_FIELDS[doctype]):
		return None
	return doc


@frappe.whitelist()
def mark_auto_draft_read(doctype, name):
	doc = _validate_target(doctype, name)
	if not doc:
		return {"read": False}
	user = frappe.session.user
	now = now_datetime()
	record_name = frappe.db.get_value("Auto Draft Read Record", {"user": user, "reference_doctype": doctype, "reference_name": name})
	if not record_name:
		try:
			frappe.get_doc({"doctype": "Auto Draft Read Record", "user": user, "reference_doctype": doctype, "reference_name": name, "first_read_at": now, "last_read_at": now}).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			pass
	return {"read": True, "doctype": doctype, "name": name}


@frappe.whitelist()
def get_unread_auto_draft_names(doctype, names=None):
	if doctype not in ALLOWED_DOCTYPES:
		return []
	names = frappe.parse_json(names) if isinstance(names, str) else (names or [])
	if not names:
		return []
	valid = _visible_names(doctype, names)
	if not valid:
		return []
	read = frappe.get_all("Auto Draft Read Record", filters={"user": frappe.session.user, "reference_doctype": doctype, "reference_name": ["in", valid]}, pluck="reference_name")
	return [name for name in valid if name not in set(read)]


@frappe.whitelist()
def get_unread_auto_draft_counts():
	result = {**dict.fromkeys(COUNT_KEYS.values(), 0), "unread_total": 0}
	for doctype, key in COUNT_KEYS.items():
		rows = _visible_names(doctype)
		read = set(frappe.get_all("Auto Draft Read Record", filters={"user": frappe.session.user, "reference_doctype": doctype, "reference_name": ["in", rows]}, pluck="reference_name")) if rows else set()
		result[key] = len([row for row in rows if row not in read])
	result["unread_total"] = sum(result[key] for key in COUNT_KEYS.values())
	return result
