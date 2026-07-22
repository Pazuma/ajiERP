import frappe
from erpnext.accounts.doctype.account.account import get_account_autoname
from frappe.model.rename_doc import rename_doc


LEGACY_LIABILITY_ROOT_NAMES = (
	"资金来源(负债)",
	"资金来源（负债）",
)
TARGET_ACCOUNT_NAME = "负债"


def execute():
	"""Rename existing Chinese liability root accounts without touching Equity."""
	legacy_accounts = frappe.get_all(
		"Account",
		filters={
			"account_name": ["in", LEGACY_LIABILITY_ROOT_NAMES],
			"parent_account": ["is", "not set"],
			"root_type": "Liability",
			"is_group": 1,
		},
		fields=["name", "company", "account_number"],
	)

	for account in legacy_accounts:
		new_name = get_account_autoname(
			account.account_number,
			TARGET_ACCOUNT_NAME,
			account.company,
		)

		if account.name == new_name:
			frappe.db.set_value(
				"Account",
				account.name,
				"account_name",
				TARGET_ACCOUNT_NAME,
				update_modified=False,
			)
			continue

		if frappe.db.exists("Account", new_name):
			frappe.log_error(
				title="Skipped legacy liability root account rename",
				message=(
					f"Cannot rename {account.name} to {new_name}: "
					"the target Account already exists."
				),
			)
			continue

		frappe.db.set_value(
			"Account",
			account.name,
			"account_name",
			TARGET_ACCOUNT_NAME,
			update_modified=False,
		)
		rename_doc(
			"Account",
			account.name,
			new_name,
			force=True,
			ignore_permissions=True,
			show_alert=False,
			rebuild_search=False,
		)
