"""China Finance additions around ERPNext's native bank reconciliation tool."""

import json
import re

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
		fields=["name", "custom_summary", "description"],
	)
	summary_map = {row.name: row.custom_summary for row in summaries}
	for row in transactions:
		stored = next((item for item in summaries if item.name == row.name), None)
		row.custom_summary = clean_bank_summary(
			(summary_map.get(row.name) or (stored.description if stored else ""))
		)
	return transactions


def clean_bank_summary(value):
	"""Keep the business summary and remove bank reference metadata from display."""
	value = (value or "").strip()
	if "｜" in value:
		value = value.split("｜", 1)[0].strip()
	value = re.split(r"\s*参考\s*#?.*$", value, maxsplit=1, flags=re.IGNORECASE)[0].strip()
	return value


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
