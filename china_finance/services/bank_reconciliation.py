"""China Finance additions around ERPNext's native bank reconciliation tool."""

import json

import frappe
from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
	create_journal_entry_bts,
	get_bank_transactions,
	reconcile_vouchers,
)


@frappe.whitelist()
def get_bank_transactions_with_summary(*args, **kwargs):
	# Frappe injects the RPC command name into whitelisted calls; the native
	# ERPNext function only accepts the business arguments.
	kwargs.pop("cmd", None)
	transactions = get_bank_transactions(*args, **kwargs)
	if not transactions:
		return transactions

	names = [row.name for row in transactions]
	summaries = frappe.get_all(
		"Bank Transaction",
		filters={"name": ["in", names]},
		fields=["name", "custom_summary"],
	)
	summary_map = {row.name: row.custom_summary for row in summaries}
	for row in transactions:
		row.custom_summary = summary_map.get(row.name) or ""
	return transactions


@frappe.whitelist()
def create_journal_entry_with_summary(remarks=None, **kwargs):
	"""Create the native editable Journal Entry draft and set its summary."""
	kwargs.pop("cmd", None)
	allow_edit = kwargs.pop("allow_edit", None)
	journal_entry = create_journal_entry_bts(**kwargs, allow_edit=True)
	if remarks:
		journal_entry.remarks = remarks
		for entry in journal_entry.accounts:
			entry.user_remark = remarks
	if allow_edit:
		return journal_entry

	journal_entry.insert()
	journal_entry.submit()
	bank_transaction = frappe.db.get_value(
		"Bank Transaction",
		kwargs["bank_transaction_name"],
		["deposit", "withdrawal"],
		as_dict=True,
	)
	paid_amount = (
		bank_transaction.deposit
		if bank_transaction.deposit > 0.0
		else bank_transaction.withdrawal
	)
	return reconcile_vouchers(
		kwargs["bank_transaction_name"],
		json.dumps([{
			"payment_doctype": "Journal Entry",
			"payment_name": journal_entry.name,
			"amount": paid_amount,
		}]),
	)
