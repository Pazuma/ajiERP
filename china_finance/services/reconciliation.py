import frappe
from frappe import _
from frappe.utils import flt, getdate

from china_finance.services.purchase_reconciliation import apply_purchase_reconciliation_statuses


@frappe.whitelist()
def generate_statement(
	company, statement_type, from_date, to_date, party=None, account=None, replaces=None, scope=None, bank_account=None,
	confirmation_method=None,
):
	frappe.only_for(("Accounts Manager", "Accounts User", "China Finance Manager"))
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	if from_date > to_date:
		frappe.throw(_("起始日期不能晚于截止日期"))

	if scope:
		scope_doc = frappe.get_doc("China Reconciliation Scope", scope)
		if scope_doc.company != company or scope_doc.scope_type != statement_type or not scope_doc.enabled:
			frappe.throw(_("对账范围与公司或对账类型不一致"))
		confirmation_method = scope_doc.confirmation_method
		if statement_type in ("Customer", "Supplier"):
			party = scope_doc.reference_name
		else:
			bank_account = scope_doc.reference_name
	if statement_type == "Bank" and bank_account:
		account = frappe.db.get_value("Bank Account", bank_account, "account")
		if not account:
			frappe.throw(_("银行账户未关联会计科目"))

	filters = {"company": company, "is_cancelled": 0, "posting_date": ["<=", to_date]}
	if statement_type in ("Customer", "Supplier"):
		filters.update({"party_type": statement_type, "party": party})
	elif statement_type == "Bank":
		filters["account"] = account
	else:
		frappe.throw(_("不支持的对账类型"))

	rows = frappe.get_all(
		"GL Entry",
		filters=filters,
		fields=["posting_date", "voucher_type", "voucher_no", "account", "remarks", "debit", "credit"],
		order_by="posting_date asc, creation asc, name asc",
	)
	opening = sum(flt(row.debit) - flt(row.credit) for row in rows if getdate(row.posting_date) < from_date)
	period_rows = [row for row in rows if getdate(row.posting_date) >= from_date]
	period_debit = sum(flt(row.debit) for row in period_rows)
	period_credit = sum(flt(row.credit) for row in period_rows)
	balance = opening
	lines = []
	for row in period_rows:
		balance += flt(row.debit) - flt(row.credit)
		lines.append({**row, "balance": balance})
	statement_basis = None
	snapshot_key = None
	ledger_snapshot = None
	if statement_type == "Customer":
		from china_finance.services.customer_reconciliation_statement import get_customer_ledger_snapshot

		snapshot = get_customer_ledger_snapshot(company, party, from_date, to_date)
		ledger_snapshot = snapshot
		statement_basis = "Ledger"
		snapshot_key = snapshot["snapshot_key"]
		opening = snapshot["opening_balance"]
		period_debit = snapshot["period_debit"]
		period_credit = snapshot["period_credit"]
		lines = snapshot["rows"]
	if statement_type == "Supplier":
		apply_purchase_reconciliation_statuses(lines)

	version = 1
	if replaces:
		version = (frappe.db.get_value("China Reconciliation Statement", replaces, "version") or 0) + 1
	doc = frappe.get_doc(
		{
			"doctype": "China Reconciliation Statement",
			"company": company,
			"scope": scope,
			"period_key": f"{from_date}|{to_date}",
		"statement_type": statement_type,
		"party_type": statement_type if statement_type in ("Customer", "Supplier") else None,
		"statement_basis": statement_basis,
			"snapshot_key": snapshot_key,
			"party": party,
			"bank_account": bank_account,
			"account": account,
			"confirmation_method": confirmation_method or ("Bank Statement" if statement_type == "Bank" else "External Confirmation"),
			"from_date": from_date,
			"to_date": to_date,
			"version": version,
			"replaces": replaces,
		"opening_balance": opening,
		"period_debit": period_debit,
		"period_credit": period_credit,
		"period_balance": ledger_snapshot["period_balance"] if ledger_snapshot else period_debit - period_credit,
		"closing_balance": opening + period_debit - period_credit,
		"currency": ledger_snapshot["currency"] if ledger_snapshot else None,
		"opening_document_count": ledger_snapshot.get("opening_document_count", 0) if ledger_snapshot else 0,
		"opening_document_total": ledger_snapshot.get("opening_document_total", 0) if ledger_snapshot else 0,
		"opening_adjustment": ledger_snapshot.get("opening_adjustment", 0) if ledger_snapshot else 0,
		"order_billing_count": ledger_snapshot.get("order_billing_count", 0) if ledger_snapshot else 0,
		"opening_documents": ledger_snapshot.get("opening_documents", []) if ledger_snapshot else [],
		"order_billing_rows": ledger_snapshot.get("order_billing_rows", []) if ledger_snapshot else [],
		"lines": lines,
		}
	)
	doc.insert()
	if statement_type == "Bank":
		from china_finance.services.reconciliation_control import refresh_bank_snapshot

		refresh_bank_snapshot(doc, save=True)
	if scope:
		from china_finance.services.reconciliation_control import carry_forward_timing_differences

		carry_forward_timing_differences(doc.name)
	return {"name": doc.name, "line_count": len(lines), "closing_balance": doc.closing_balance}
