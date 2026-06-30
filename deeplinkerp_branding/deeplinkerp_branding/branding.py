import frappe


BRAND_NAME = "Deeplinkerp"
BRAND_LOGO_URL = "/assets/deeplinkerp_branding/logo/deeplinkerp_logo_radius.png?v=erpnext-bg-067efb"
ERP_NEXT_NAME = "ERPNext"
DEEPLINKERP_ICON_NAME = "Deeplinkerp"
FRAPPE_FRAMEWORK_NAME = "Frappe Framework"
DLP_FRAMEWORK_NAME = "DLP Framework"
FRAMEWORK_ICON_NAME = "Framework"
FRAPPE_FRAMEWORK_ICON_NAMES = (FRAMEWORK_ICON_NAME, FRAPPE_FRAMEWORK_NAME)
DLP_FRAMEWORK_ALLOWED_ROLE = "System Manager"
DLP_ERP_IDX = 0
DLP_FRAMEWORK_IDX = -1
SETTINGS_DOCNAME = "Deeplinkerp Settings"
SETTINGS_LABEL = "Deeplinkerp Settings"
SETTINGS_ICON_URL = "/assets/erpnext/icons/desktop_icons/solid/erpnext_settings.svg"
PRODUCT_APP_NAMES = {"ai_assistant", "mes_integration"}
PRODUCT_APP_BY_TITLE = {
	"AI Assistant": "ai_assistant",
	"Mes Integration": "mes_integration",
	"MES Integration": "mes_integration",
	"MES Integration Log": "mes_integration",
}
PRODUCT_MODULE_APP_KEYS = {
	"ai assistant": "ai_assistant",
	"ai_assistant": "ai_assistant",
	"mes integration": "mes_integration",
	"mes_integration": "mes_integration",
	"mes integration log": "mes_integration",
	"mes_integration_log": "mes_integration",
}

SIDEBAR_ITEM_FIELDS = (
	"child",
	"collapsible",
	"display_depends_on",
	"filters",
	"icon",
	"indent",
	"keep_closed",
	"label",
	"link_to",
	"link_type",
	"navigate_to_tab",
	"route_options",
	"show_arrow",
	"type",
	"url",
)


def apply_deeplinkerp_settings_branding():
	"""Replace the ERPNext Settings desktop entry with Deeplinkerp Settings."""
	apply_logo_branding()

	if frappe.db.exists("Desktop Icon", "Deeplinkerp Branding"):
		frappe.db.set_value("Desktop Icon", "Deeplinkerp Branding", "hidden", 1, update_modified=False)

	apply_erpnext_desktop_icon_branding()
	apply_framework_desktop_icon_branding()
	apply_settings_desktop_icon_branding()

	copy_erpnext_settings_sidebar_items()

	if frappe.db.exists("Workspace", SETTINGS_DOCNAME):
		frappe.db.set_value(
			"Workspace",
			SETTINGS_DOCNAME,
			{"app": "deeplinkerp_branding", "label": SETTINGS_LABEL, "title": SETTINGS_LABEL},
			update_modified=False,
		)

	if frappe.db.exists("Workspace Sidebar", SETTINGS_DOCNAME):
		frappe.db.set_value(
			"Workspace Sidebar",
			SETTINGS_DOCNAME,
			{"app": "deeplinkerp_branding", "standard": 1, "title": SETTINGS_LABEL},
			update_modified=False,
		)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def apply_erpnext_desktop_icon_branding():
	if not frappe.db.exists("Desktop Icon", DEEPLINKERP_ICON_NAME):
		icon = frappe.new_doc("Desktop Icon")
		icon.update(
			{
				"doctype": "Desktop Icon",
				"name": DEEPLINKERP_ICON_NAME,
				"label": BRAND_NAME,
				"app": "deeplinkerp_branding",
				"hidden": 1,
				"icon_type": "App",
				"idx": DLP_ERP_IDX,
				"link": "/desk/home",
				"link_type": "External",
				"logo_url": BRAND_LOGO_URL,
				"standard": 1,
			}
		)
		icon.flags.ignore_permissions = True
		icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.db.set_value(
		"Desktop Icon",
		DEEPLINKERP_ICON_NAME,
		{
			"app": "deeplinkerp_branding",
			"hidden": 1,
			"icon_type": "App",
			"idx": DLP_ERP_IDX,
			"label": BRAND_NAME,
			"link": "/desk/home",
			"link_type": "External",
			"logo_url": BRAND_LOGO_URL,
			"standard": 1,
		},
		update_modified=False,
	)

	children = frappe.get_all(
		"Desktop Icon", filters={"parent_icon": ["in", [ERP_NEXT_NAME, DEEPLINKERP_ICON_NAME]]}, pluck="name"
	)
	for child in children:
		frappe.db.set_value("Desktop Icon", child, "parent_icon", "", update_modified=False)

	for icon_name in (ERP_NEXT_NAME, "ERPNext Settings"):
		if frappe.db.exists("Desktop Icon", icon_name):
			frappe.delete_doc("Desktop Icon", icon_name, force=1, ignore_permissions=True)



def apply_settings_desktop_icon_branding():
	if not frappe.db.exists("Desktop Icon", SETTINGS_DOCNAME):
		icon = frappe.new_doc("Desktop Icon")
		icon.update(
			{
				"doctype": "Desktop Icon",
				"name": SETTINGS_DOCNAME,
				"label": SETTINGS_LABEL,
				"app": "deeplinkerp_branding",
				"hidden": 0,
				"icon_type": "Link",
				"idx": 10,
				"link_to": SETTINGS_DOCNAME,
				"link_type": "Workspace Sidebar",
				"logo_url": SETTINGS_ICON_URL,
				"standard": 1,
			}
		)
		icon.flags.ignore_permissions = True
		icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.db.set_value(
		"Desktop Icon",
		SETTINGS_DOCNAME,
		{
			"app": "deeplinkerp_branding",
			"hidden": 0,
			"icon_type": "Link",
			"label": SETTINGS_LABEL,
			"idx": 10,
			"link_to": SETTINGS_DOCNAME,
			"link_type": "Workspace Sidebar",
			"logo_url": SETTINGS_ICON_URL,
			"standard": 1,
		},
		update_modified=False,
	)


def apply_framework_desktop_icon_branding():
	if not frappe.db.exists("Desktop Icon", DLP_FRAMEWORK_NAME):
		icon = frappe.new_doc("Desktop Icon")
		icon.update(
			{
				"doctype": "Desktop Icon",
				"name": DLP_FRAMEWORK_NAME,
				"label": DLP_FRAMEWORK_NAME,
				"app": "deeplinkerp_branding",
				"hidden": 0,
				"icon_type": "App",
				"idx": DLP_FRAMEWORK_IDX,
				"link": "/desk/build",
				"link_type": "External",
				"logo_url": BRAND_LOGO_URL,
				"standard": 1,
				"roles": [{"role": DLP_FRAMEWORK_ALLOWED_ROLE}],
			}
		)
		icon.flags.ignore_permissions = True
		icon.insert(ignore_permissions=True, ignore_if_duplicate=True)

	frappe.db.set_value(
		"Desktop Icon",
		DLP_FRAMEWORK_NAME,
		{
			"app": "deeplinkerp_branding",
			"hidden": 0,
			"icon_type": "App",
			"idx": DLP_FRAMEWORK_IDX,
			"label": DLP_FRAMEWORK_NAME,
			"link": "/desk/build",
			"link_type": "External",
			"logo_url": BRAND_LOGO_URL,
			"standard": 1,
		},
		update_modified=False,
	)
	set_desktop_icon_roles(DLP_FRAMEWORK_NAME, [DLP_FRAMEWORK_ALLOWED_ROLE])

	children = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", FRAPPE_FRAMEWORK_ICON_NAMES]}, pluck="name")
	for child in children:
		frappe.db.set_value("Desktop Icon", child, "parent_icon", DLP_FRAMEWORK_NAME, update_modified=False)

	for icon_name in FRAPPE_FRAMEWORK_ICON_NAMES:
		if frappe.db.exists("Desktop Icon", icon_name):
			frappe.delete_doc("Desktop Icon", icon_name, force=1, ignore_permissions=True)

def apply_logo_branding():
	for doctype in ("System Settings", "Website Settings"):
		if frappe.db.exists("DocType", doctype):
			frappe.db.set_single_value(doctype, "app_name", BRAND_NAME, update_modified=False)

	for doctype in ("Navbar Settings", "Website Settings"):
		if frappe.db.exists("DocType", doctype):
			frappe.db.set_single_value(doctype, "app_logo", BRAND_LOGO_URL, update_modified=False)


def set_desktop_icon_roles(icon_name, roles):
	if not frappe.db.exists("Desktop Icon", icon_name):
		return

	icon = frappe.get_doc("Desktop Icon", icon_name)
	existing_roles = [row.role for row in icon.roles]
	if existing_roles == roles:
		return

	icon.set("roles", [])
	for role in roles:
		icon.append("roles", {"role": role})

	icon.flags.ignore_permissions = True
	icon.save(ignore_permissions=True)


def can_access_dlp_framework():
	return frappe.session.user == "Administrator" or DLP_FRAMEWORK_ALLOWED_ROLE in frappe.get_roles()


def apply_boot_branding(bootinfo):
	"""Brand app labels in bootinfo before the desk sidebar is rendered."""
	app_data = bootinfo.get("app_data", [])
	workspace_sidebar_item = bootinfo.get("workspace_sidebar_item", {})
	module_app = bootinfo.get("module_app", {})
	show_dlp_framework = can_access_dlp_framework()

	for app in app_data:
		app_name = app.get("app_name")
		if app_name == "erpnext" or app.get("app_title") == ERP_NEXT_NAME:
			app["app_title"] = BRAND_NAME
		elif app_name == "frappe" or app.get("app_title") == FRAPPE_FRAMEWORK_NAME:
			app["app_title"] = DLP_FRAMEWORK_NAME
		elif app_name in PRODUCT_APP_NAMES:
			app["app_title"] = BRAND_NAME

	for key, app_name in PRODUCT_MODULE_APP_KEYS.items():
		module_app[key] = app_name

	for key, sidebar in workspace_sidebar_item.items():
		label = sidebar.get("label")
		module = sidebar.get("module")
		if sidebar.get("app") in PRODUCT_APP_NAMES:
			continue
		if label in PRODUCT_APP_BY_TITLE:
			sidebar["app"] = PRODUCT_APP_BY_TITLE[label]
		elif module in PRODUCT_APP_BY_TITLE:
			sidebar["app"] = PRODUCT_APP_BY_TITLE[module]
		elif key in PRODUCT_MODULE_APP_KEYS:
			sidebar["app"] = PRODUCT_MODULE_APP_KEYS[key]

	filtered_icons = []
	for icon in bootinfo.get("desktop_icons", []):
		if icon.get("parent_icon") in {ERP_NEXT_NAME, DEEPLINKERP_ICON_NAME}:
			icon["parent_icon"] = ""
		elif icon.get("parent_icon") in {FRAPPE_FRAMEWORK_NAME, FRAMEWORK_ICON_NAME}:
			icon["parent_icon"] = DLP_FRAMEWORK_NAME
		elif icon.get("parent_icon") in PRODUCT_APP_BY_TITLE:
			icon["parent_icon"] = BRAND_NAME

		if icon.get("name") == ERP_NEXT_NAME or icon.get("label") == ERP_NEXT_NAME:
			icon["hidden"] = 1
		elif icon.get("name") == DEEPLINKERP_ICON_NAME or icon.get("label") == BRAND_NAME:
			icon["app"] = "deeplinkerp_branding"
			icon["hidden"] = 1
			icon["label"] = BRAND_NAME
			icon["logo_url"] = BRAND_LOGO_URL
			icon["link"] = "/desk/home"
			icon["link_type"] = "External"
		elif icon.get("name") == "ERPNext Settings" or icon.get("label") == "ERPNext Settings":
			icon["hidden"] = 1
		elif icon.get("name") == FRAMEWORK_ICON_NAME or icon.get("label") == FRAMEWORK_ICON_NAME:
			icon["hidden"] = 1
		elif icon.get("name") == DLP_FRAMEWORK_NAME or icon.get("label") == DLP_FRAMEWORK_NAME:
			if not show_dlp_framework:
				continue
			icon["app"] = "deeplinkerp_branding"
			icon["hidden"] = 0
			icon["label"] = DLP_FRAMEWORK_NAME
			icon["logo_url"] = BRAND_LOGO_URL

		if icon.get("parent_icon") == DLP_FRAMEWORK_NAME and not show_dlp_framework:
			continue

		filtered_icons.append(icon)

	bootinfo["desktop_icons"] = filtered_icons


def append_unique(values, value):
	if value not in values:
		values.append(value)



def copy_erpnext_settings_sidebar_items():
	if not (
		frappe.db.exists("Workspace Sidebar", "ERPNext Settings")
		and frappe.db.exists("Workspace Sidebar", SETTINGS_DOCNAME)
	):
		return

	source = frappe.get_doc("Workspace Sidebar", "ERPNext Settings")
	target = frappe.get_doc("Workspace Sidebar", SETTINGS_DOCNAME)

	target.set("items", [])
	for source_item in source.items:
		target.append(
			"items",
			{field: source_item.get(field) for field in SIDEBAR_ITEM_FIELDS if source_item.get(field) is not None},
		)

	target.flags.ignore_permissions = True
	target.flags.ignore_links = True
	target.save(ignore_permissions=True)
