"""Idempotent Stock sidebar entries owned by client_akivision."""

import frappe


SIDEBAR_NAME = "Stock"


def sync_stock_sidebar_entries():
	"""Keep the Stock master-data section label stable after migrations."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": SIDEBAR_NAME},
		fields=["name", "idx", "label", "type"],
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

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()
