"""Idempotent Manufacturing sidebar entries owned by client_akivision."""

import frappe

from client_akivision.utils.buying_sidebar import _create_item, _ensure_single_link, _reindex


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
	_ensure_single_link(
		items,
		link_type="DocType",
		link_to="Timesheet",
		label="工时记录",
		icon="clock",
		child=1,
		parent=SIDEBAR_NAME,
	)

	# Put the setting at the end of the native Tools group.  The older one-shot
	# patch only inserted it on newly created sidebars, so it could be absent or
	# left after Reports/Settings on deployed sites.
	items = _move_to_end_of_tools(_get_items(), settings.name)
	_reindex(items)
	group_manufacturing_sidebar_entries()

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def group_manufacturing_sidebar_entries():
	"""Pin production forms and Plant Floor before the remaining grouped links."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return
	items = _get_items()
	# BOM remains available in master data; hide only its production navigation.
	for item in items:
		if item.link_type == "DocType" and item.link_to == "BOM":
			frappe.db.delete("Workspace Sidebar Item", {"name": item.name})
	items = _get_items()
	ordered = [item for item in items if item.type == "Link"
		and item.link_type in {"Workspace", "Dashboard"} and item.link_to == SIDEBAR_NAME]
	for target in ("Work Order", "Job Card", "Stock Entry", "Timesheet", "Plant Floor"):
		ordered.extend(item for item in items if item.type == "Link"
			and item.link_type == "DocType" and item.link_to == target)
	used = {item.name for item in ordered}
	for item in ordered:
		frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 0, update_modified=False)
	for labels, report in (({"其他表单", "Other Forms"}, False), ({"报表", "Reports"}, True)):
		links = [item for item in items if item.type == "Link" and item.name not in used
			and (item.link_type == "Report") == report]
		if not links:
			continue
		section = next((item for item in items if item.type in SECTION_TYPES and item.label in labels), None)
		if not section:
			section = _create_item({"type": "Section Break", "label": "报表" if report else "其他表单"}, parent=SIDEBAR_NAME)
		frappe.db.set_value("Workspace Sidebar Item", section.name,
			{"child": 0, "collapsible": 1, "keep_closed": 1}, update_modified=False)
		ordered.append(section)
		used.add(section.name)
		for item in links:
			frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 1, update_modified=False)
			ordered.append(item)
			used.add(item.name)
	for item in items:
		if item.type in SECTION_TYPES and item.name not in used:
			frappe.db.delete("Workspace Sidebar Item", {"name": item.name})
	_reindex(ordered)
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
