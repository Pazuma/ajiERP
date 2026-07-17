"""Idempotent Buying sidebar entries owned by client_akivision."""

import frappe


SIDEBAR_NAME = "Buying"


def sync_buying_sidebar_entries():
	"""Keep native Buying links in the Akivision sidebar layout."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = _get_items()
	masters_section = _find_section(items, {"Setup", "设置", "Master", "Masters", "主数据"})
	if masters_section:
		frappe.db.set_value(
			"Workspace Sidebar Item",
			masters_section.name,
			"label",
			"Masters",
			update_modified=False,
		)
		masters_section.label = "Masters"

	purchase_receipt = _ensure_single_link(
		items,
		link_type="DocType",
		link_to="Purchase Receipt",
		label="Purchase Receipt",
		icon="receipt-text",
		child=0,
	)
	items = _move_after(items, purchase_receipt.name, "Purchase Order")
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


def _find_section(items, labels):
	section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
	return next((item for item in items if item.type in section_types and item.label in labels), None)


def _ensure_single_link(items, *, link_type, link_to, label, icon, child):
	matches = [
		item for item in items if item.type == "Link" and item.link_type == link_type and item.link_to == link_to
	]
	item = matches[0] if matches else None

	for duplicate in matches[1:]:
		frappe.delete_doc("Workspace Sidebar Item", duplicate.name, force=True, ignore_permissions=True)
		items.remove(duplicate)

	if not item:
		item = _create_item(
			{
				"label": label,
				"type": "Link",
				"link_type": link_type,
				"link_to": link_to,
				"icon": icon,
				"child": child,
			}
		)
		items.append(item)
	else:
		frappe.db.set_value(
			"Workspace Sidebar Item",
			item.name,
			{"label": label, "icon": icon, "child": child},
			update_modified=False,
		)
		item.label = label

	return item


def _create_item(values):
	item = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar Item",
			"parent": SIDEBAR_NAME,
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
	return frappe._dict(
		{
			"name": item.name,
			"idx": item.idx,
			"label": item.label,
			"type": item.type,
			"link_type": item.link_type,
			"link_to": item.link_to,
		}
	)


def _move_after(items, item_name, anchor_link_to):
	target = next(item for item in items if item.name == item_name)
	ordered = [item for item in items if item.name != item_name]
	anchor_index = next(
		(
			index
			for index, item in enumerate(ordered)
			if item.type == "Link" and item.link_type == "DocType" and item.link_to == anchor_link_to
		),
		None,
	)
	if anchor_index is None:
		return items
	ordered.insert(anchor_index + 1, target)
	return ordered


def _reindex(items):
	for idx, item in enumerate(items, start=1):
		frappe.db.set_value("Workspace Sidebar Item", item.name, "idx", idx, update_modified=False)
