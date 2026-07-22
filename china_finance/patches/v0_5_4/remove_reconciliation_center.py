import frappe

PAGE_NAME = "china-reconciliation-center"


def execute():
	"""Remove the retired China Reconciliation Center page and its navigation links.

	The feature was removed from the app; clean up any stale Page record and
	leftover Workspace/Sidebar links so the navigation sync cannot preserve
	them as custom entries. Idempotent and safe to re-run.
	"""
	if frappe.db.exists("Page", PAGE_NAME):
		frappe.delete_doc("Page", PAGE_NAME, force=1, ignore_permissions=True)

	if frappe.db.exists("Workspace", "China Finance"):
		workspace = frappe.get_doc("Workspace", "China Finance")
		kept = [link for link in workspace.links if link.link_to != PAGE_NAME]
		if len(kept) != len(workspace.links):
			workspace.set("links", kept)
			workspace.flags.ignore_permissions = True
			workspace.save()

	if frappe.db.exists("Workspace Sidebar", "China Finance"):
		sidebar = frappe.get_doc("Workspace Sidebar", "China Finance")
		kept = [item for item in sidebar.items if item.link_to != PAGE_NAME]
		if len(kept) != len(sidebar.items):
			sidebar.set("items", kept)
			sidebar.flags.ignore_permissions = True
			sidebar.save()
