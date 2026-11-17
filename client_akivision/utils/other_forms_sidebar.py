"""Move low-frequency DocType links into one module-local Other Forms group."""

import json
from pathlib import Path

import frappe


SECTION_TYPES = {"Section Break", "Card Break", "Sidebar Item Group"}
SECTION_LABELS = {"其他表单", "Other Forms"}
COMMON_SECTION_LABELS = {"常用表单", "Common Forms"}
REPORT_LABELS = {"Reports", "报表", "Other Reports", "其他报表"}
SETTINGS_LABELS = {"Settings", "设置"}
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "other_forms_sidebar.json"

def sync_other_forms_sidebar_entries():
	"""Synchronize configured common and low-frequency form links."""
	config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
	changed = False
	for module_name, definition in config.items():
		sidebar_name = _select_sidebar(definition)
		if not sidebar_name:
			frappe.logger("client_akivision").warning("Other Forms skipped: no sidebar for %s", module_name)
			continue
			for link in definition.get("links", []):
				if link.get("link_type") == "DocType" and not frappe.db.exists("DocType", link.get("link_to")):
					frappe.logger("client_akivision").warning(
						"Other Forms target DocType does not exist: %s (%s)", link.get("link_to"), module_name
					)
		if _sync_sidebar(
			sidebar_name,
			common_link_definitions=definition.get("common_links", []),
			other_link_definitions=definition.get("links", []),
		):
			changed = True
	# Common-link pinning above must not flatten the purchasing workflow groups.
	from client_akivision.utils.buying_sidebar import group_buying_sidebar_entries
	group_buying_sidebar_entries()
	from client_akivision.utils.manufacturing_sidebar import group_manufacturing_sidebar_entries
	group_manufacturing_sidebar_entries()
	from client_akivision.utils.selling_sidebar import persist_selling_groups
	persist_selling_groups()
	from client_akivision.utils.stock_sidebar import group_stock_sidebar_entries
	group_stock_sidebar_entries()
	if changed:
		frappe.cache.delete_key("bootinfo")
		frappe.clear_cache()


def _select_sidebar(definition):
	targets = {(item["link_type"], item["link_to"]) for item in definition.get("links", [])}
	for sidebar_name in definition.get("sidebars", []):
		if not frappe.db.exists("Workspace Sidebar", sidebar_name):
			continue
		items = _get_items(sidebar_name)
		if any(item.type == "Link" and (item.link_type, item.link_to) in targets for item in items):
			return sidebar_name
	return next(
		(name for name in definition.get("sidebars", []) if frappe.db.exists("Workspace Sidebar", name)),
		None,
	)


def _sync_sidebar(sidebar_name, common_link_definitions, other_link_definitions):
	items = _get_items(sidebar_name)
	common_targets = {(item["link_type"], item["link_to"]) for item in common_link_definitions}
	other_targets = {(item["link_type"], item["link_to"]) for item in other_link_definitions}
	if not common_targets and not other_targets and not _find_common_sections(items):
		return False

	changed = False
	common_links, common_changed = _ensure_links(
		sidebar_name, items, common_link_definitions, common_targets, child=0
	)
	other_links, other_changed = _ensure_links(
		sidebar_name, items, other_link_definitions, other_targets, child=1
	)
	changed = common_changed or other_changed
	items = _get_items(sidebar_name)
	common_sections = _find_common_sections(items)
	if common_sections:
		_remove_common_sections(items, common_targets)
		changed = True
		items = _get_items(sidebar_name)

	other_section = _find_section(items)
	if other_links and not other_section:
		other_section = _create_item(
			sidebar_name,
			{"label": "其他表单", "type": "Section Break", "child": 0},
		)
		changed = True
		items = _get_items(sidebar_name)

	common_names = {item.name for item in common_links}
	other_names = {item.name for item in other_links}
	block_names = common_names | other_names
	ordered = [item for item in items if item.name not in block_names]
	if common_links:
		ordered = _place_pinned_links(ordered, common_links)
	if other_section and other_links:
		ordered = _place_other_forms_block(ordered, other_section, other_links)

	if [item.name for item in ordered] != [item.name for item in items]:
		changed = True
	_reindex(ordered)
	return changed


def _find_section(items):
	return next((item for item in items if item.type in SECTION_TYPES and item.label in SECTION_LABELS), None)


def _find_common_sections(items):
	return [item for item in items if item.type in SECTION_TYPES and item.label in COMMON_SECTION_LABELS]


def _remove_common_sections(items, common_targets):
	"""Remove legacy Common Forms headings without deleting links below them."""
	sections = _find_common_sections(items)
	section_names = {section.name for section in sections}
	orphaned_links = []
	for index, section in enumerate(items):
		if section.name not in section_names:
			continue
		end_index = next(
			(
				candidate_index
				for candidate_index, candidate in enumerate(items[index + 1 :], start=index + 1)
				if candidate.type in SECTION_TYPES
			),
			len(items),
		)
		# Only child links belong to a section. Root links can appear between a
		# legacy heading and the next section and must not keep that heading alive.
		section_links = [
			item for item in items[index + 1 : end_index] if item.type == "Link" and item.child
		]
		undeclared_links = [
			item for item in section_links if (item.link_type, item.link_to) not in common_targets
		]
		if undeclared_links:
			orphaned_links.extend(undeclared_links)
			frappe.logger("client_akivision").warning(
				"Preserved Common Forms section with undeclared links: %s",
				", ".join(item.label or item.link_to or item.name for item in undeclared_links),
			)
			continue
		_delete_sidebar_item(section.name)
	return orphaned_links


def _ensure_links(sidebar_name, items, definitions, targets, child):
	"""Return the first existing link per target, creating missing valid DocTypes."""
	by_target = {}
	duplicate_names = []
	for item in items:
		key = (item.link_type, item.link_to)
		if item.type == "Link" and key in targets and key not in by_target:
			by_target[key] = item
		elif item.type == "Link" and key in targets:
			duplicate_names.append(item.name)

	for item_name in duplicate_names:
		_delete_sidebar_item(item_name)

	changed = False
	for definition in definitions:
		key = (definition["link_type"], definition["link_to"])
		if key in by_target:
			label = definition.get("label")
			updates = {}
			if label and by_target[key].label != label:
				updates["label"] = label
			if by_target[key].child != child:
				updates["child"] = child
			if updates:
				frappe.db.set_value(
					"Workspace Sidebar Item", by_target[key].name, updates, update_modified=False
				)
				for field, value in updates.items():
					setattr(by_target[key], field, value)
				changed = True
			continue
		if definition["link_type"] == "DocType" and not frappe.db.exists("DocType", definition["link_to"]):
			continue
		if definition["link_type"] == "Report" and not frappe.db.exists("Report", definition["link_to"]):
			continue
		item = _create_item(
			sidebar_name,
			{
				"label": definition.get("label", definition["link_to"]),
				"type": "Link",
				"link_type": definition["link_type"],
				"link_to": definition["link_to"],
				"child": child,
			},
		)
		by_target[key] = item
		changed = True

	return [
		by_target[(definition["link_type"], definition["link_to"])]
		for definition in definitions
		if (definition["link_type"], definition["link_to"]) in by_target
	], changed or bool(duplicate_names)


def _delete_sidebar_item(item_name):
	"""Delete a sidebar child row without enqueueing dynamic-link cleanup."""
	frappe.db.delete("Workspace Sidebar Item", {"name": item_name})


def _place_pinned_links(items, links):
	"""Place high-frequency links at the sidebar root, before business sections."""
	block_names = {item.name for item in links}
	remaining = [item for item in items if item.name not in block_names]
	insert_at = next(
		(
			index + 1
			for index, item in enumerate(remaining)
			if item.type == "Link" and item.link_type in {"Workspace", "Dashboard"}
		),
		0,
	)
	remaining[insert_at:insert_at] = links
	return remaining


def _place_other_forms_block(items, section, links):
	"""Keep Other Forms after business sections and before reports/settings."""
	block_names = {section.name, *(item.name for item in links)}
	remaining = [item for item in items if item.name not in block_names]
	insert_at = next(
		(
			index
			for index, item in enumerate(remaining)
			if item.type in SECTION_TYPES and item.label in REPORT_LABELS | SETTINGS_LABELS
		),
		len(remaining),
	)
	remaining[insert_at:insert_at] = [section, *links]
	return remaining


def _get_items(sidebar_name):
	return frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": sidebar_name},
		fields=["name", "idx", "label", "type", "link_type", "link_to", "icon", "child"],
		order_by="idx, creation",
	)


def _create_item(sidebar_name, values):
	item = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar Item",
			"parent": sidebar_name,
			"parenttype": "Workspace Sidebar",
			"parentfield": "items",
			"idx": 9999,
			"collapsible": 1,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 0,
			**values,
		}
	)
	item.insert(ignore_permissions=True)
	return frappe._dict({"name": item.name, **values})


def _reindex(items):
	for idx, item in enumerate(items, start=1):
		frappe.db.set_value("Workspace Sidebar Item", item.name, "idx", idx, update_modified=False)
