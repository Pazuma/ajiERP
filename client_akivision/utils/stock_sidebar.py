"""Idempotent Stock sidebar entries owned by client_akivision."""

import frappe

from client_akivision.utils.buying_sidebar import _ensure_single_link, _reindex


SIDEBAR_NAME = "Stock"

# Chinese link labels that must survive fixture re-syncs, without touching
# translations so other modules keep showing 送货单.
LINK_LABELS = {
	"Purchase Receipt": "采购入库",
	"Delivery Note": "销售出库",
}


def sync_stock_sidebar_entries():
	"""Keep the Stock master-data section label stable after migrations."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": SIDEBAR_NAME},
		fields=["name", "idx", "label", "type", "link_type", "link_to"],
		order_by="idx, creation",
	)
	section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
	masters_section = next(
		(
			item
			for item in items
			if item.type in section_types
			and item.label in {"Setup", "设置", "Master", "Masters", "主数据"}
		),
		None,
	)
	if masters_section:
		frappe.db.set_value(
			"Workspace Sidebar Item",
			masters_section.name,
			"label",
			"Masters",
			update_modified=False,
		)

	for item in items:
		target = LINK_LABELS.get(item.link_to)
		if item.type == "Link" and target and item.label != target:
			frappe.db.set_value(
				"Workspace Sidebar Item",
				item.name,
				"label",
				target,
				update_modified=False,
			)

	# Remove any Bin link previously created under the wrong sidebar.
	for misplaced in frappe.get_all(
		"Workspace Sidebar Item",
		filters={"link_to": "Bin", "parent": ["!=", SIDEBAR_NAME]},
		pluck="name",
	):
		frappe.delete_doc("Workspace Sidebar Item", misplaced, force=True, ignore_permissions=True)

	bin_item = _ensure_single_link(
		items,
		link_type="DocType",
		link_to="Bin",
		label="Bin",
		icon="warehouse",
		child=0,
		parent=SIDEBAR_NAME,
	)
	items = _move_after_dashboard(items, bin_item.name)
	_reindex(items)

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def _move_after_dashboard(items, item_name):
	"""Place the Bin link right below the Dashboard (数据面板) entry."""
	target = next(item for item in items if item.name == item_name)
	ordered = [item for item in items if item.name != item_name]
	anchor_index = next(
		(
			index
			for index, item in enumerate(ordered)
			if item.type == "Link" and item.link_type == "Dashboard"
		),
		None,
	)
	if anchor_index is None:
		return items
	ordered.insert(anchor_index + 1, target)
	return ordered
