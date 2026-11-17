"""Item entry presentation; standard document permissions remain authoritative."""
import frappe

FULL_ROLE = "完整物料查看者"


def ensure_schema():
	if not frappe.db.exists("Role", FULL_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": FULL_ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def configure_entries(bootinfo):
	sidebars = bootinfo.get("workspace_sidebar_item", {})
	for key, view in (("buying", "purchase"), ("stock", "stock")):
		for item in sidebars.get(key, {}).get("items", []):
			if item.get("link_type") == "DocType" and item.get("link_to") == "Item":
				item.update({"link_type": "URL", "link_to": f"/app/item?item_view={view}"})
	if set(frappe.get_roles()).intersection({FULL_ROLE, "System Manager"}) and frappe.has_permission("Item", "read"):
		sidebar = sidebars.setdefault("kpi dashboard", {"title": "KPI Dashboard", "name": "KPI Dashboard", "items": []})
		if sidebar and not any(item.get("link_to") == "/app/item?item_view=full" for item in sidebar.get("items", [])):
			sidebar.setdefault("items", []).append({"type": "Link", "label": "完整物料表", "link_type": "URL", "link_to": "/app/item?item_view=full", "icon": "package", "child": 0})
