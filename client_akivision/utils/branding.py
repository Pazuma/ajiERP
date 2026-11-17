"""Company branding overrides for the initial website and Desk render."""

SPLASH_IMAGE = "/assets/client_akivision/images/aki_vision_logo.png?v=2026110201"


def update_context(context):
	return {"splash_image": SPLASH_IMAGE}


def apply_boot_branding(bootinfo):
	"""Rename the framework entry without changing its saved identity or links."""
	for icon in bootinfo.get("desktop_icons", []):
		if icon.get("label") == "Deeplinkerp Settings":
			icon["label"] = "AKI Setting"
			icon["logo_url"] = "/assets/client_akivision/images/company_desktop_icons/erpnext/solid/erpnext_settings.svg?v=2026110201"
			icon["app"] = "client_akivision"
		if icon.get("parent_icon") == "Deeplinkerp Settings":
			icon["parent_icon"] = "AKI Setting"
		if icon.get("label") == "DLP Framework":
			icon["label"] = "AKI"
			icon["logo_url"] = "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110201"
			icon["app"] = "client_akivision"
		if icon.get("parent_icon") == "DLP Framework":
			icon["parent_icon"] = "AKI"


def sync_login_logo():
    """Use the company logo for login, signup and password recovery screens."""
    import frappe

    frappe.db.set_single_value("Website Settings", "app_logo", SPLASH_IMAGE)
    frappe.clear_cache()
