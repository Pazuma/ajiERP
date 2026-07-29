import frappe


NOTIFICATION_DOCTYPES = (
	("Draft Notification Rule", "Draft Notification Rule"),
	("Draft Notification Log", "Draft Notification Log"),
	("DingTalk Robot Config", "DingTalk Robot Config"),
)


def execute():
	"""Keep Draft Notifications links under the Notifications section."""
	if not frappe.db.exists("Workspace Sidebar", "System"):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", "System")
	names = {doctype for doctype, _ in NOTIFICATION_DOCTYPES}
	items = [
		item
		for item in sidebar.items
		if not (item.type == "Link" and item.link_type == "DocType" and item.link_to in names)
	]

	notifications_index = next(
		(
			index
			for index, item in enumerate(items)
			if item.type == "Section Break" and item.label == "Notifications"
		),
		None,
	)
	if notifications_index is None:
		return

	insert_at = notifications_index + 1
	while insert_at < len(items) and items[insert_at].child:
		insert_at += 1

	new_items = [
		{
			"type": "Link",
			"label": label,
			"link_type": "DocType",
			"link_to": doctype,
			"child": 1,
			"indent": 0,
			"collapsible": 1,
			"keep_closed": 0,
			"show_arrow": 0,
		}
		for doctype, label in NOTIFICATION_DOCTYPES
	]
	sidebar.set("items", items[:insert_at] + new_items + items[insert_at:])
	sidebar.save(ignore_permissions=True)
