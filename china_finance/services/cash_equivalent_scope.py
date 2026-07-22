import hashlib
import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime


def get_effective_cash_scope(company, as_of_date, reviewed_only=False):
	as_of_date = getdate(as_of_date)
	rows = frappe.get_all(
		"China Cash Equivalent Scope",
		filters={"company": company, "effective_from": ["<=", as_of_date]},
		fields=[
			"name", "account", "classification", "included", "restricted", "restriction_reason",
			"policy_basis", "effective_from", "effective_to", "reviewed", "reviewed_by", "reviewed_on",
		], order_by="account, effective_from desc",
	)
	active = {}
	for row in rows:
		if row.account in active or (row.effective_to and getdate(row.effective_to) < as_of_date):
			continue
		if reviewed_only and not row.reviewed:
			continue
		active[row.account] = row
	return list(active.values())


def get_cash_scope_accounts(company, as_of_date, require_reviewed=False):
	rows = get_effective_cash_scope(company, as_of_date, reviewed_only=require_reviewed)
	return [row.account for row in rows if row.included and row.classification != "排除项"]


def get_cash_scope_hash(company, as_of_date):
	rows = [dict(row) for row in get_effective_cash_scope(company, as_of_date)]
	payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)
	return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@frappe.whitelist()
def get_cash_equivalent_scope(company, as_of_date=None):
	frappe.has_permission("Company", "read", company, throw=True)
	return get_effective_cash_scope(company, as_of_date or frappe.utils.today())


@frappe.whitelist()
def review_cash_equivalent_scope(name, notes=None):
	frappe.only_for(("System Manager", "China Finance Manager"))
	doc = frappe.get_doc("China Cash Equivalent Scope", name)
	doc.check_permission("write")
	doc.db_set({
		"reviewed": 1, "reviewed_by": frappe.session.user,
		"reviewed_on": now_datetime(), "review_notes": notes,
	})
	return {"name": name, "reviewed": 1}
