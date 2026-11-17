"""Read-only APIs used by the BOM detail form."""

import frappe
from frappe import _
from frappe.utils import cint, flt

from client_akivision.utils.bom import get_item_code


def _root_row(doc):
	item_code = get_item_code(doc.item)
	return {
		"model_code": doc.get("custom_bom_code") or f"BOM-{item_code}",
		"level": 0,
		"item_code": item_code,
		"item_name": doc.item_name,
		"drawing_no": doc.get("custom_engineering_drawing_no"),
		"drawing_revision": doc.get("custom_engineering_drawing_revision"),
		"qty": doc.quantity,
		"uom": doc.uom,
		"parent_bom": None,
		"bom_no": doc.name,
	}


def _component_row(root, parent_bom, level, row):
	return {
		"model_code": root.get("custom_bom_code") or f"BOM-{get_item_code(root.item)}",
		"level": level,
		"item_code": row.item_code,
		"item_name": row.item_name,
		"drawing_no": row.get("custom_engineering_drawing_no"),
		"drawing_revision": row.get("custom_engineering_drawing_revision"),
		"qty": row.qty,
		"uom": row.uom,
		"parent_bom": parent_bom,
		"bom_no": row.bom_no,
	}


@frappe.whitelist()
def get_exploded_structure(bom):
	"""Return the BOM tree for display without exposing inaccessible child BOMs."""
	if not bom:
		frappe.throw(_("请先保存 BOM 后再查看展开结构。"))

	root = frappe.get_doc("BOM", bom)
	root.check_permission("read")
	rows = [_root_row(root)]

	def append_components(parent, level, path, factor=1):
		for item in parent.get("items", []):
			rows.append(_component_row(root, parent.name, level, item))
			rows[-1]["cumulative_qty"] = item.qty * factor
			if not item.bom_no or item.do_not_explode:
				continue
			if item.bom_no in path:
				rows[-1]["structure_warning"] = _("检测到循环 BOM，已停止展开。")
				continue
			child = frappe.get_doc("BOM", item.bom_no)
			if not child.has_permission("read"):
				rows[-1]["structure_warning"] = _("无权查看子 BOM 明细。")
				continue
			append_components(child, level + 1, path | {child.name}, item.qty * factor / child.quantity)

	append_components(root, 1, {root.name})
	return {"bom": root.name, "rows": rows}


@frappe.whitelist()
def get_bom_list_entries():
	"""Permission-filtered representative records, selected before list pagination."""
	rows = frappe.get_list("BOM", fields=["name", "item", "docstatus", "is_active", "is_default", "modified"],
		order_by="modified desc, name asc", limit_page_length=0)
	def priority(row):
		if row.docstatus == 1 and row.is_active and row.is_default:
			return 0
		if row.docstatus == 0:
			return 1
		if row.docstatus == 1 and row.is_active:
			return 2
		return 3
	entries = {}
	for row in sorted(rows, key=priority):
		entries.setdefault(row.item, row.name)
	return list(entries.values())


@frappe.whitelist()
def get_bom_versions(bom):
	"""Return the amendment chain for the same business BOM and item."""
	current = frappe.get_doc("BOM", bom)
	current.check_permission("read")
	code = current.get("custom_bom_code") or f"BOM-{get_item_code(current.item)}"
	rows = frappe.get_list(
		"BOM",
		filters={"item": current.item, "company": current.company},
		fields=["name", "docstatus", "is_active", "is_default", "amended_from", "custom_version_source", "custom_version_no", "custom_first_activated_at", "creation", "modified"],
		order_by="creation asc",
		limit_page_length=0,
	)
	status = {0: _("草稿"), 1: _("已提交"), 2: _("已取消")}
	for index, row in enumerate(rows, 1):
		row["version_no"] = row.custom_version_no or index
		row["amended_from"] = row.custom_version_source or row.amended_from
		row["status_label"] = status.get(row.docstatus, str(row.docstatus))
		row["is_current"] = row.name == current.name
		row["is_current_default"] = row.docstatus == 1 and bool(row.is_active and row.is_default) and frappe.db.get_value("Item", current.item, "default_bom") == row.name
		row["first_activated_at"] = row.custom_first_activated_at
		row["display_status"] = ("草稿" if row.docstatus == 0 else "已取消" if row.docstatus == 2 else "已停用" if not row.is_active else "当前启用" if row.is_current_default else "历史有效")
	return {"business_code": code, "item": current.item, "rows": rows}


@frappe.whitelist()
def get_bom_version_view(bom, version_bom, expand_children=0):
	base = frappe.get_doc("BOM", bom)
	target = frappe.get_doc("BOM", version_bom)
	for doc in (base, target):
		doc.check_permission("read")
	if any(base.get(key) != target.get(key) for key in ("item", "company")):
		frappe.throw("只能查看同物料、同公司的 BOM 版本。")
	versions = get_bom_versions(bom)["rows"]
	summary = next((r for r in versions if r.name == target.name), None)
	if not summary:
		frappe.throw("无权查看所选版本。", frappe.PermissionError)
	return _build_bom_version_view(target, summary, expand_children=cint(expand_children))


@frappe.whitelist()
def preview_bom_draft(doc, expand_children=0):
	"""Preview unsaved component edits without writing BOMs or activating versions."""
	target = frappe.get_doc(frappe.parse_json(doc))
	if target.doctype != "BOM" or target.docstatus != 0:
		frappe.throw("只能预览 BOM 草稿。")
	if not frappe.db.exists("BOM", target.name):
		frappe.has_permission("BOM", "create", throw=True)
		frappe.get_doc("Item", target.item).check_permission("read")
	else:
		saved = frappe.get_doc("BOM", target.name)
		saved.check_permission("read")
		saved.check_permission("write")
		if saved.docstatus != 0 or saved.item != target.item or saved.company != target.company:
			frappe.throw("仅允许预览当前草稿，不能修改已提交版本。")
	return _build_bom_version_view(
		target, dict(name=target.name, docstatus=0, is_current_default=False), expand_children=cint(expand_children)
	)


def _build_bom_version_view(target, summary, expand_children=False):
	items = []
	warnings = []
	identity = frappe.db.get_value("Item", target.item, ["custom_internal_model", "custom_external_model"], as_dict=True) or {}
	model = identity.get("custom_external_model") or target.get("custom_excel_model") or get_item_code(target.item)
	def append(doc, level, factor, path):
		for row in doc.items:
			if not row.item_code:
				continue
			qty = flt(row.qty)
			drawing_no = row.bom_no or row.get("custom_engineering_drawing_no") or row.get("custom_excel_drawing_no") or ""
			items.append(dict(model=model, level=level,
				item_name=row.get("custom_excel_item_name") or row.item_name, drawing_no=drawing_no, qty=qty * factor))
			if not expand_children or not row.bom_no or row.do_not_explode:
				continue
			if row.bom_no in path:
				warnings.append("检测到循环子 BOM，停止展开。")
				continue
			child = frappe.get_doc("BOM", row.bom_no)
			if not child.has_permission("read"):
				warnings.append("无权查看部分子 BOM 明细。")
				continue
			if child.docstatus != 1 or not child.is_active or not flt(child.quantity):
				warnings.append("部分子 BOM 无效或产出数量为零，停止展开。")
				continue
			append(child, level + 1, factor * qty / flt(child.quantity), path | {child.name})
	items.append(dict(model=model, level=0,
		item_name=identity.get("custom_internal_model") or "", drawing_no=target.get("custom_bom_code") or "", qty=target.quantity))
	append(target, 1, 1, {target.name})
	return dict(summary=dict(summary, business_code=target.custom_bom_code, quantity=target.quantity, uom=target.uom, company=target.company),
		items=items, warnings=warnings, costs=dict(currency=target.currency, raw_material_cost=target.raw_material_cost, operating_cost=target.operating_cost, total_cost=target.total_cost))
