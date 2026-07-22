import frappe


def execute():
	from china_finance.setup.install import sync_navigation_metadata

	if frappe.db.exists("Workspace", "China Finance"):
		sync_navigation_metadata()
