"""Optional navigation visibility, independent of document/role permissions."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


ENTRIES = (
	("custom_show_kpi_module", "指标看板", "KPI Dashboard"),
	("custom_show_master_data_module", "基础资料", "基础资料"),
)


def ensure_schema():
	fields = [{
		"fieldname": "custom_module_access_section", "fieldtype": "Section Break",
		"label": "自定义模块访问", "insert_after": "modules_html", "permlevel": 1,
		"description": "仅控制导航显示，不授予或撤销角色、页面及单据权限。",
		"hidden": 1,
	}]
	previous = "custom_module_access_section"
	for fieldname, label, _ in ENTRIES:
		fields.append({
			"fieldname": fieldname, "fieldtype": "Check", "label": label,
			"default": "1", "insert_after": previous, "permlevel": 1,
			"hidden": 1,
		})
		previous = fieldname
	create_custom_fields({"User": fields}, update=True)
	# Move existing opt-outs into the native module selection exactly once:
	# reset the retired flag after copying it, so repeated migrations are safe.
	for fieldname, _, sidebar in ENTRIES:
		for row in frappe.get_all("User", filters={fieldname: 0}, pluck="name"):
			user = frappe.get_doc("User", row)
			if sidebar not in {item.module for item in user.block_modules}:
				user.append("block_modules", {"module": sidebar}).db_insert()
			frappe.db.set_value("User", row, fieldname, 1, update_modified=False)
			frappe.clear_document_cache("User", row)


def add_module_options(doc, method=None):
	"""Extend the native editor without replacing its save/profile behavior."""
	modules = list(doc.get_onload("all_modules") or [])
	for _, _, sidebar in ENTRIES:
		if sidebar not in modules:
			modules.append(sidebar)
	doc.set_onload("all_modules", modules)


def configure_entries(bootinfo):
	"""Run last so other boot hooks cannot restore a hidden custom entry."""
	blocked = set(frappe.get_cached_doc("User", frappe.session.user).get_blocked_modules())
	blocked.update(frappe.get_cached_doc("User", "Administrator").get_blocked_modules())
	for _, _, sidebar in ENTRIES:
		if sidebar not in blocked:
			continue
		bootinfo.get("workspace_sidebar_item", {}).pop(sidebar.lower(), None)
		bootinfo["desktop_icons"] = [icon for icon in bootinfo.get("desktop_icons", [])
			if not (icon.get("name") == sidebar or icon.get("label") == sidebar
				or (icon.get("link_type") == "Workspace Sidebar" and icon.get("link_to") == sidebar))]
