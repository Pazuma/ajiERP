import frappe


AI_ASSISTANT_LOGO_URL = "/assets/deeplinkerp_branding/logo/AI%20Assistant_logo.png?v=erpnext-bg-067efb"


def ensure_ai_assistant_sidebar_visible():
	"""Keep AI Assistant visible for non-admin Desk users.

	Frappe filters Workspace Sidebar records by the user's allowed modules. The
	ai_assistant app has a Page but no readable DocType, so normal users do not
	get the AI Assistant module in allow_modules. Leaving the sidebar module blank
	makes the public Page link eligible for all users who can access ai-chat.
	"""
	if frappe.db.exists("Workspace Sidebar", "AI Assistant"):
		frappe.db.set_value(
			"Workspace Sidebar",
			"AI Assistant",
			{
				"app": "ai_assistant",
				"module": "",
				"standard": 1,
			},
			update_modified=False,
		)
		sidebar = frappe.get_doc("Workspace Sidebar", "AI Assistant")
		existing = {(row.link_type, row.link_to) for row in sidebar.items}
		if ("Page", "ai-chat") not in existing:
			sidebar.append("items", {
				"icon": "panel-top",
				"idx": 1,
				"label": "企业智能业务助手",
				"link_to": "ai-chat",
				"link_type": "Page",
				"type": "Link",
			})
		if ("DocType", "AI Assistant Settings") not in existing:
			sidebar.append("items", {
				"icon": "settings",
				"idx": 2,
				"label": "AI Assistant Settings",
				"link_to": "AI Assistant Settings",
				"link_type": "DocType",
				"type": "Link",
			})
		for idx, row in enumerate(sidebar.items, start=1):
			row.idx = idx
		sidebar.flags.ignore_permissions = True
		sidebar.save(ignore_permissions=True)

	if frappe.db.exists("Desktop Icon", "AI Assistant"):
		frappe.db.set_value(
			"Desktop Icon",
			"AI Assistant",
			{
				"app": "ai_assistant",
				"hidden": 0,
				"link_to": "AI Assistant",
				"link_type": "Workspace Sidebar",
				"logo_url": AI_ASSISTANT_LOGO_URL,
				"standard": 1,
				"idx": 0,
			},
			update_modified=False,
		)

	if frappe.db.exists("Page", "ai-chat"):
		page = frappe.get_doc("Page", "ai-chat")
		if "All" not in {row.role for row in page.roles}:
			page.append("roles", {"role": "All"})
			page.flags.ignore_permissions = True
			page.save(ignore_permissions=True)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()
