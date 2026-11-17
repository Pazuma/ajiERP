"""Keep daily quality work visible and secondary forms under Setup."""

import frappe

from client_akivision.utils.buying_sidebar import _ensure_single_link, _reindex


def sync_quality_sidebar_entries():
	if not frappe.db.exists("Workspace Sidebar", "Quality"):
		return
	items = frappe.get_all("Workspace Sidebar Item", filters={"parent": "Quality"},
		fields=["name", "idx", "label", "type", "link_type", "link_to"], order_by="idx, creation")
	target = _ensure_single_link(items, link_type="Report", link_to="Quality Nonconforming Items",
		label="质量不合格", icon="clipboard-x", child=0, parent="Quality")
	ordered = [item for item in items if item.name != target.name]
	index = next((i + 1 for i, item in enumerate(ordered)
		if item.link_type == "DocType" and item.link_to == "Quality Inspection"), 0)
	ordered.insert(index, target)
	setup = next((item for item in ordered
		if item.type == "Section Break" and item.label in {"Setup", "设置"}), None)
	if setup:
		secondary_doctypes = {
			"Quality Goal", "Quality Review", "Quality Action",
			"Non Conformance", "Quality Feedback", "Quality Meeting",
		}
		secondary = [item for item in ordered
			if item.type == "Link" and item.link_type == "DocType"
			and item.link_to in secondary_doctypes]
		secondary_names = {item.name for item in secondary}
		ordered = [item for item in ordered if item.name not in secondary_names]
		for item in secondary:
			frappe.db.set_value("Workspace Sidebar Item", item.name, "child", 1, update_modified=False)
		index = next(i + 1 for i, item in enumerate(ordered) if item.name == setup.name)
		ordered[index:index] = secondary
	_reindex(ordered)
	frappe.clear_cache()
