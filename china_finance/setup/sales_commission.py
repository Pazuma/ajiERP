"""Idempotent commissioning setup; does not assign privileges to existing users."""

import frappe


def ensure_schema():
	for role in ("销售总监", "Sales Commission Manager", "Sales Commission Finance", "Sales Commission Margin Reader"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc(dict(doctype="Role", role_name=role, desk_access=1)).insert(ignore_permissions=True)
	for doctype, fields, name in (
		("Sales Commission Sheet", ["sales_order", "status"], "commission_order_status"),
		("Sales Commission Receipt Allocation", ["source_key", "status"], "commission_source_status"),
		("Sales Commission Disbursement", ["sales_order", "sales_person", "status"], "commission_payment_scope"),
	):
		if frappe.db.table_exists(doctype):
			frappe.db.add_index(doctype, fields, name)
	ensure_sidebar()
	ensure_order_page()


def ensure_order_page():
	if not frappe.db.exists("Page", "sales-commission-orders"):
		frappe.reload_doc("china_finance", "page", "sales_commission_orders")
	if not frappe.db.exists("Workspace Sidebar", "Selling"):
		return
	sidebar = frappe.get_doc("Workspace Sidebar", "Selling")
	entry = next((r for r in sidebar.items if r.link_type == "Page" and r.link_to == "sales-commission-orders"), None)
	if not entry:
		entry = sidebar.append("items", dict(type="Link", link_type="Page", link_to="sales-commission-orders", label="销售提成单", icon="sheet", child=0))
	# Place before the Reports section: the boot whitelist filters that section
	# before grouping top-level links, so appending at its end hides the Page.
	items = [r for r in sidebar.items if r != entry]
	position = next((i + 1 for i, r in enumerate(items) if r.link_to == "Sales Invoice"), 0)
	items.insert(position, entry)
	if list(sidebar.items) != items or entry.child or entry.is_new():
		entry.child = 0
		for index, item in enumerate(items, 1):
			item.idx = index
		sidebar.set("items", items)
		sidebar.save(ignore_permissions=True)


def ensure_sidebar():
	"""Add a shared, server-scoped commission table without replacing navigation."""
	if not frappe.db.exists("Workspace Sidebar", "Selling") or not frappe.db.exists("Report", "Sales Commission Management"):
		return
	sidebar = frappe.get_doc("Workspace Sidebar", "Selling")
	if not any(row.link_type == "Report" and row.link_to == "Sales Commission Management" for row in sidebar.items):
		sidebar.append("items", dict(type="Link", link_type="Report", link_to="Sales Commission Management", label="提成管理", icon="sheet", child=0))
		sidebar.save(ignore_permissions=True)

