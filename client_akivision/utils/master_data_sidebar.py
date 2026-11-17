"""Idempotent desktop and sidebar entries for existing master data."""

import frappe


SIDEBAR_NAME = "基础资料"
ICON_NAME = SIDEBAR_NAME
ICON_URL = "/assets/erpnext/icons/desktop_icons/solid/stock.svg?v=master-data-blue-1"

SECTIONS = (
	(
		"往来与人员",
		"users",
		(
			("客户", "Customer", "users"),
			("供应商", "Supplier", "users"),
			("业务人员", "Sales Person", "user"),
			("员工", "Employee", "employee"),
		),
	),
	(
		"物料与库存",
		"package",
		(
			("物料表", "Item", "package"),
			("产品表", "sales-products", "package", "Page"),
			("BOM汇总", "BOM", "layers"),
			("物料分类", "Item Group", "folder"),
			("计量单位", "UOM", "scale"),
			("仓库", "Warehouse", "warehouse"),
			("储位", "Bin", "warehouse"),
			("品牌", "Brand", "tag"),
		),
	),
	(
		"地址与联系人",
		"map-pin",
		(
			("地址表", "Address", "map-pin"),
			("联系人", "Contact", "contact"),
		),
	),
)


def _link_type(link):
	return link[3] if len(link) > 3 else "DocType"


def _can_access_link(label, target, link_type):
	if link_type == "Page":
		if not frappe.db.exists("Page", target):
			return False
		page = frappe.get_doc("Page", target)
		page_roles = [row.role for row in page.roles]
		return not page_roles or bool(set(page_roles).intersection(frappe.get_roles()))
	return frappe.db.exists("DocType", target) and frappe.has_permission(target, "read")


def sync_master_data_sidebar():
	"""Create a navigation-only module backed by existing ERPNext doctypes."""
	ensure_master_data_sidebar()
	ensure_master_data_desktop_icon()
	_clear_navigation_cache()


def configure_boot_entries(bootinfo):
	"""Expose the module in the current boot response before a migrate is run."""
	sidebars = bootinfo.setdefault("workspace_sidebar_item", frappe._dict())
	sidebar_key = SIDEBAR_NAME.lower()
	if not sidebars.get(sidebar_key):
		items = []
		for section_label, section_icon, links in SECTIONS:
			allowed_links = [
				(label, target, icon, _link_type(link))
				for link in links
				for label, target, icon in [link[:3]]
				if _can_access_link(label, target, _link_type(link))
			]
			if not allowed_links:
				continue
			items.append(
				frappe._dict(
					{
						"label": section_label,
						"type": "Section Break",
						"icon": section_icon,
						"child": 0,
					}
				)
			)
			items.extend(
				frappe._dict(
					{
						"label": label,
						"link_to": target,
						"link_type": link_type,
						"type": "Link",
						"icon": icon,
						"child": 1,
					}
				)
				for label, target, icon, link_type in allowed_links
			)
		if items:
			sidebars[sidebar_key] = frappe._dict(
				{
					"label": SIDEBAR_NAME,
					"items": items,
					"header_icon": "database",
					"module": "",
					"app": "client_akivision",
				}
			)

	if not sidebars.get(sidebar_key):
		return

	# Existing sites receive the new entry on their next boot as well as migrate.
	items = sidebars[sidebar_key].get("items", [])
	if _can_access_link("产品表", "sales-products", "Page") and not any(
		item.get("link_type") == "Page" and item.get("link_to") == "sales-products" for item in items
	):
		position = next((i + 1 for i, item in enumerate(items) if item.get("link_to") == "Item"), len(items))
		items.insert(position, frappe._dict(label="产品表", link_to="sales-products", link_type="Page", type="Link", icon="package", child=1))
	for key, sidebar in sidebars.items():
		sidebar["items"] = [row for row in sidebar.get("items", [])
			if row.get("link_to") != "Product List"]
	items = sidebars[sidebar_key].get("items", [])
	if frappe.has_permission("BOM", "read") and not any(item.get("link_to") == "BOM" for item in items):
		position = next((i + 1 for i, item in enumerate(items) if item.get("link_to") == "Item"), len(items))
		items.insert(position, frappe._dict(label="BOM汇总", link_to="BOM", link_type="DocType", type="Link", icon="layers", child=1))
	for sidebar in sidebars.values():
		for item in sidebar.get("items", []):
			if item.get("link_type") == "DocType" and item.get("link_to") == "BOM":
				item["label"] = "BOM汇总"

	desktop_icons = bootinfo.setdefault("desktop_icons", [])
	existing_icon = next((icon for icon in desktop_icons if icon.get("label") == SIDEBAR_NAME), None)
	icon_values = {
		"name": ICON_NAME,
		"app": "client_akivision",
		"label": SIDEBAR_NAME,
		"hidden": 0,
		"icon": "database",
		"icon_type": "Link",
		"link_to": SIDEBAR_NAME,
		"link_type": "Workspace Sidebar",
		# DesktopIcon skips route generation when sidebar is populated.
		"sidebar": None,
		"logo_url": ICON_URL,
		"bg_color": "blue",
		"standard": 1,
	}
	if existing_icon:
		existing_icon.update(icon_values)
		return
	icon_values["idx"] = max((icon.get("idx") or 0 for icon in desktop_icons), default=0) + 1
	desktop_icons.append(frappe._dict(icon_values))


def ensure_master_data_sidebar():
	"""Create or repair the dedicated sidebar without touching master records."""
	if frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR_NAME)
	else:
		sidebar = frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"name": SIDEBAR_NAME,
				"title": SIDEBAR_NAME,
				"app": "client_akivision",
				"module": "",
				"standard": 1,
				"header_icon": "database",
			}
		)
		sidebar.flags.ignore_permissions = True
		sidebar.insert(ignore_permissions=True)

	sidebar.title = SIDEBAR_NAME
	sidebar.app = "client_akivision"
	sidebar.standard = 1
	sidebar.header_icon = "database"

	existing_links = {
		(row.link_type, row.link_to): row
		for row in sidebar.items
		if row.type == "Link" and row.link_type and row.link_to
	}
	owned_links = {
		(_link_type(link), link[1])
		for _, _, links in SECTIONS
		for link in links
	}
	kept_custom_rows = [
		row
		for row in sidebar.items
		if not (row.type == "Link" and (row.link_type, row.link_to) in owned_links)
		and not (row.type == "Link" and row.link_type == "DocType" and row.link_to == "Product List")
		and not (row.type == "Section Break" and row.label in {section[0] for section in SECTIONS})
	]

	ordered_rows = []
	for section_label, section_icon, links in SECTIONS:
		ordered_rows.append(
			frappe._dict(
				{
					"label": section_label,
					"icon": section_icon,
					"type": "Section Break",
					"child": 0,
				}
			)
		)
		for link in links:
			label, target, icon = link[:3]
			link_type = _link_type(link)
			if not _can_access_link(label, target, link_type):
				continue
			row = existing_links.get((link_type, target)) or frappe._dict()
			row.update(
				{
					"label": label,
					"icon": icon,
					"type": "Link",
					"link_type": link_type,
					"link_to": target,
					"child": 1,
					"collapsible": 1,
					"indent": 0,
					"keep_closed": 0,
					"show_arrow": 0,
				}
			)
			ordered_rows.append(row)

	# Preserve future/manual links that are not owned by this module.
	ordered_rows.extend(kept_custom_rows)
	sidebar.set("items", ordered_rows)
	for idx, row in enumerate(sidebar.items, start=1):
		row.idx = idx

	sidebar.flags.ignore_permissions = True
	sidebar.save(ignore_permissions=True)
	# Workspace Sidebar derives a module during save. Keep it blank so visibility
	# comes from each linked DocType permission rather than one source module.
	frappe.db.set_value(
		"Workspace Sidebar",
		SIDEBAR_NAME,
		{"app": "client_akivision", "module": "", "standard": 1},
		update_modified=False,
	)


def ensure_master_data_desktop_icon():
	"""Expose the sidebar as a desktop module; item permissions drive visibility."""
	values = {
		"app": "client_akivision",
		"label": SIDEBAR_NAME,
		"hidden": 0,
		"bg_color": "blue",
		"icon": "database",
		"icon_type": "Link",
		"idx": _next_desktop_index(),
		"link": None,
		"link_to": SIDEBAR_NAME,
		"link_type": "Workspace Sidebar",
		"sidebar": None,
		"logo_url": ICON_URL,
		"standard": 1,
	}
	if frappe.db.get_value("Desktop Icon", ICON_NAME, "name"):
		frappe.db.set_value("Desktop Icon", ICON_NAME, values, update_modified=False)
		return

	icon = frappe.get_doc({"doctype": "Desktop Icon", "name": ICON_NAME, **values})
	icon.flags.ignore_permissions = True
	icon.insert(ignore_permissions=True, ignore_if_duplicate=True)


def _next_desktop_index():
	existing_idx = frappe.db.get_value("Desktop Icon", ICON_NAME, "idx")
	if existing_idx is not None:
		return existing_idx
	return (frappe.db.get_value("Desktop Icon", {}, "idx", order_by="idx desc") or 0) + 1


def _clear_navigation_cache():
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()
