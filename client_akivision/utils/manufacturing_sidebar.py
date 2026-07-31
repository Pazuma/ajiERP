"""Idempotent Manufacturing sidebar entries owned by client_akivision."""

import frappe

from client_akivision.utils.buying_sidebar import _ensure_single_link, _reindex


SIDEBAR_NAME = "Manufacturing"
SECTION_TYPES = {"Section Break", "Card Break", "Sidebar Item Group"}
TOOLS_LABELS = {"Tools", "工具"}


def sync_manufacturing_sidebar_entries():
	"""Keep drawing configuration visible inside the Manufacturing tools group."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = _get_items()
	settings = _ensure_single_link(
		items,
		link_type="DocType",
		link_to="Engineering Drawing Settings",
		label="Engineering Drawing Settings",
		icon="settings",
		child=1,
		parent=SIDEBAR_NAME,
	)

	# Put the setting at the end of the native Tools group.  The older one-shot
	# patch only inserted it on newly created sidebars, so it could be absent or
	# left after Reports/Settings on deployed sites.
	items = _move_to_end_of_tools(_get_items(), settings.name)
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


def _move_to_end_of_tools(items, item_name):
	target = next(item for item in items if item.name == item_name)
	ordered = [item for item in items if item.name != item_name]
	tools_index = next(
		(
			index
			for index, item in enumerate(ordered)
			if item.type in SECTION_TYPES and item.label in TOOLS_LABELS
		),
		None,
	)
	if tools_index is None:
		return ordered + [target]

	next_section_index = next(
		(
			index
			for index, item in enumerate(ordered[tools_index + 1 :], start=tools_index + 1)
			if item.type in SECTION_TYPES
		),
		len(ordered),
	)
	ordered.insert(next_section_index, target)
	return ordered
