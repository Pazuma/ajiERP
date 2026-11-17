"""Idempotent Stock sidebar entries owned by client_akivision."""

import frappe

from client_akivision.utils.buying_sidebar import _ensure_single_link, _reindex


SIDEBAR_NAME = "Stock"

# Chinese link labels that must survive fixture re-syncs, without touching
# translations so other modules keep showing 送货单.
LINK_LABELS = {
	"Purchase Receipt": "采购入库",
	"Delivery Note": "销售出库",
	"Material Stocktake Summary": "物料库存汇总清点单",
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
	stocktake_item = _ensure_single_link(
		items,
		link_type="DocType",
		link_to="Material Stocktake Summary",
		label="物料库存汇总清点单",
		icon="clipboard-check",
		child=0,
		parent=SIDEBAR_NAME,
	)
	if frappe.db.exists("Report", "物料折旧汇总"):
		_ensure_single_link(
			items, link_type="Report", link_to="物料折旧汇总",
			label="物料折旧汇总", icon="chart-line", child=1, parent=SIDEBAR_NAME,
		)
	items = _move_after_dashboard(items, bin_item.name)
	items = _move_after_item(items, stocktake_item.name, bin_item.name)
	_reindex(items)
	group_stock_sidebar_entries()

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def group_stock_sidebar_entries():
	"""Put every uncategorized inventory link in one final ``其他表单`` group."""
	items = frappe.get_all("Workspace Sidebar Item", filters={"parent": SIDEBAR_NAME},
		fields=["name", "label", "type", "link_type", "link_to"], order_by="idx, creation")
	links = [item for item in items if item.type == "Link"]
	for item in list(links):
		if item.link_to == "Product List":
			frappe.delete_doc("Workspace Sidebar Item", item.name, ignore_permissions=True)
			links.remove(item)
	groups = [
		("入库与出库", ["Material Request", "Pick List", "Packing Slip"]),
	]
	# Reports are determined by their link type, plus Quick Stock Balance which
	# is shipped in ERPNext's Reports section as a DocType link.
	report_links = [item for item in links if item.link_type == "Report" or item.link_to == "Quick Stock Balance"]
	used = set()
	ordered = []

	def append_section(label, target_links, *, keep_closed=True):
		section = next((item for item in items if item.type == "Section Break"
			and item.label in {label, "Reports" if label == "报表" else label}), None)
		if not section:
			section = frappe.get_doc({"doctype": "Workspace Sidebar Item", "parent": SIDEBAR_NAME,
				"parenttype": "Workspace Sidebar", "parentfield": "items",
				"type": "Section Break", "label": label}).insert(ignore_permissions=True)
		frappe.db.set_value("Workspace Sidebar Item", section.name,
			{"label": label, "child": 0, "collapsible": 1, "keep_closed": int(keep_closed)}, update_modified=False)
		ordered.append(section)
		used.add(section.name)
		seen_targets = set()
		for target in target_links:
			matches = [item for item in links if item.name not in used and item.link_to == target]
			for item in matches:
				# Do not show duplicate navigation rows (not duplicate business data).
				if item.link_to in seen_targets:
					frappe.delete_doc("Workspace Sidebar Item", item.name, ignore_permissions=True)
					used.add(item.name)
					continue
				seen_targets.add(item.link_to)
				used.add(item.name)
				frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 1, update_modified=False)
				ordered.append(item)

		return section

	# Keep only Home and Dashboard outside a section at the top.
	for item in links:
		if item.link_type == "Workspace" and item.link_to == SIDEBAR_NAME:
			frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 0, update_modified=False)
			ordered.insert(0, item)
			used.add(item.name)
		elif item.link_type == "Dashboard" and item.link_to == SIDEBAR_NAME:
			frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 0, update_modified=False)
			ordered.append(item)
			used.add(item.name)

	# Keep the screenshot's six selected entries at the sidebar root, including
	# Outbound List even though its link type is Report.
	for target in ("Stock Entry", "Purchase Receipt", "Delivery Note",
		"Outbound List", "Material Stocktake Summary"):
		for item in links:
			if item.link_to == target and item.name not in used:
				frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 0, update_modified=False)
				ordered.append(item)
				used.add(item.name)
	for label, targets in groups:
		append_section(label, targets)
	append_section("报表", [item.link_to for item in report_links])

	# This is deliberately last: every remaining link, regardless of its
	# original native section, is now easy to find under Other Forms.
	other_targets = [item for item in links if item.name not in used]
	append_section("其他表单", [item.link_to for item in other_targets])

	# Remove obsolete empty/native section headings after their links moved.
	for item in items:
		if item.type == "Section Break" and item.name not in used:
			frappe.delete_doc("Workspace Sidebar Item", item.name, ignore_permissions=True)
	_reindex(ordered)
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


def _move_after_item(items, item_name, anchor_name):
	"""Place a link immediately after an existing sidebar item."""
	if item_name == anchor_name:
		return items
	ordered = [item for item in items if item.name != item_name]
	anchor_index = next((index for index, item in enumerate(ordered) if item.name == anchor_name), None)
	if anchor_index is None:
		return items
	target = next(item for item in items if item.name == item_name)
	ordered.insert(anchor_index + 1, target)
	return ordered
