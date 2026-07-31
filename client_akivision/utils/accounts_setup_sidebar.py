"""Idempotent Accounts Setup sidebar entries owned by client_akivision."""

import frappe

from client_akivision.utils.buying_sidebar import _ensure_single_link, _reindex


SIDEBAR_NAME = "Accounts Setup"
SECTION_TYPES = {"Section Break", "Card Break", "Sidebar Item Group"}
SETUP_LABELS = {"Setup", "设置"}


def sync_accounts_setup_sidebar_entries():
	"""Keep Payment Terms Template in the Accounts Setup section."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = _get_items()
	payment_terms = _ensure_single_link(
		items,
		link_type="DocType",
		link_to="Payment Terms Template",
		label="Payment Terms Template",
		icon="",
		child=1,
		parent=SIDEBAR_NAME,
	)
	items = _move_after_setup(_get_items(), payment_terms.name)
	_reindex(items)

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def _get_items():
	return frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": SIDEBAR_NAME},
		fields=["name", "idx", "label", "type", "link_type", "link_to"],
		order_by="idx, creation",
	)


def _move_after_setup(items, item_name):
	target = next(item for item in items if item.name == item_name)
	ordered = [item for item in items if item.name != item_name]
	setup_index = next(
		(
			index
			for index, item in enumerate(ordered)
			if item.type in SECTION_TYPES and item.label in SETUP_LABELS
		),
		None,
	)
	if setup_index is None:
		return ordered + [target]
	ordered.insert(setup_index + 1, target)
	return ordered
