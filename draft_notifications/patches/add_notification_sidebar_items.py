import frappe


NOTIFICATION_DOCTYPES = (
	("Draft Notification Rule", "Draft Notification Rule"),
	("Draft Notification Log", "Draft Notification Log"),
	("DingTalk Robot Config", "DingTalk Robot Config"),
)


def execute():
	"""Add Draft Notifications DocTypes to the system sidebar idempotently."""
	if not frappe.db.exists("Workspace Sidebar", "System"):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", "System")
	notifications_index = next(
		(
			index
			for index, item in enumerate(sidebar.items)
			if item.type == "Section Break" and item.label == "Notifications"
		),
		None,
	)
	if notifications_index is None:
		return

	insert_at = notifications_index + 1
	while insert_at < len(sidebar.items) and sidebar.items[insert_at].child:
		insert_at += 1

	existing = {
		(item.link_type, item.link_to)
		for item in sidebar.items
		if item.type == "Link"
	}
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
		if ("DocType", doctype) not in existing
	]

	if new_items:
		sidebar.set("items", sidebar.items[:insert_at] + new_items + sidebar.items[insert_at:])
		sidebar.save(ignore_permissions=True)
