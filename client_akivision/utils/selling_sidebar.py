"""Idempotent Selling sidebar entries owned by client_akivision."""

import frappe


SIDEBAR_NAME = "Selling"
REPORTS = (
	("Delivery List", "送货清单"),
	("Sales Order List", "销售订单清单"),
)


def sync_selling_sidebar_entries():
	"""Restore required Selling links without changing unrelated entries."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_NAME):
		return

	items = _get_items()
	existing_product_link = next((item for item in items if item.type == "Link" and item.link_type == "Page"
		and item.link_to == "sales-products"), None)
	item_link = next((item for item in items if item.type == "Link" and item.link_type == "DocType"
		and item.link_to == "Item"), None)
	item_position = items.index(item_link) if item_link else None
	if item_link:
		frappe.delete_doc("Workspace Sidebar Item", item_link.name, ignore_permissions=True)
		items.remove(item_link)
	price_link = next((item for item in items if item.type == "Link" and item.link_type == "DocType"
		and item.link_to == "Item Price"), None)
	price_position = items.index(price_link) if price_link else None
	if price_link:
		frappe.delete_doc("Workspace Sidebar Item", price_link.name, ignore_permissions=True)
		items.remove(price_link)
	_masters_section = _find_section(items, {"Setup", "设置", "Masters", "主数据"})
	if _masters_section:
		frappe.db.set_value(
			"Workspace Sidebar Item", _masters_section.name, "label", "Masters", update_modified=False
		)
		_masters_section.label = "Masters"
	product_link = _ensure_link(items, link_type="Page", link_to="sales-products",
		label="产品表", icon="package", child=0)
	if item_position is not None:
		items.remove(product_link)
		items.insert(min(item_position, len(items)), product_link)
	elif price_position is not None:
		items.remove(product_link)
		items.insert(min(price_position, len(items)), product_link)
	elif _masters_section and not existing_product_link:
		items = _place_after(items, [product_link.name], _masters_section.name)

	# ERPNext's fixture labels this native DocType as Tax Template. Keep its
	# technical link unchanged while using the business-facing label.
	for item in items:
		if item.type == "Link" and item.link_type == "DocType" and item.link_to == "Sales Taxes and Charges Template":
			frappe.db.set_value(
				"Workspace Sidebar Item",
				item.name,
				"label",
				"Sales Taxes and Charges Template",
				update_modified=False,
			)
			item.label = "Sales Taxes and Charges Template"
			break

	delivery_note = _ensure_link(
		items,
		link_type="DocType",
		link_to="Delivery Note",
		label="Delivery Note",
		icon="truck",
		child=0,
	)
	items = _move_after(items, delivery_note.name, "Sales Order")
	_ensure_link(
		items,
		link_type="DocType",
		link_to="Sample Loan Out",
		label="借出样品单",
		icon="package",
		child=0,
	)

	_ensure_link(items, link_type="DocType", link_to="Sample Loan In", label="借回样品单", icon="package", child=0)
	reports_section = _find_section(items, {"报表", "Reports"})
	if not reports_section:
		reports_section = _create_item(
			{"label": "Reports", "type": "Section Break", "icon": "sheet", "child": 0}
		)
		items.append(reports_section)

	report_items = [
		_ensure_link(
			items,
			link_type="Report",
			link_to=report_name,
			label=label,
			icon="",
			child=1,
		)
		for report_name, label in REPORTS
	]
	items = _place_after(items, [item.name for item in report_items], reports_section.name)
	_reindex(items)
	persist_selling_groups()

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def hide_selling_item_entry():
	"""Hide only the raw material list entry in the Selling sidebar."""
	for item in _get_items():
		if item.type == "Link" and item.link_type == "DocType" and item.link_to == "Item":
			frappe.delete_doc("Workspace Sidebar Item", item.name, ignore_permissions=True)
	_reindex(_get_items())
	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def persist_selling_groups():
	"""Persist the grouped order so sidebar reloads use the same layout."""
	from client_akivision.utils.workspace_sidebar import group_selling_sidebar

	sidebar = {"items": _get_items()}
	group_selling_sidebar(sidebar)
	for item in sidebar["items"]:
		if item.name and item.name.startswith("selling-group-"):
			section = _create_item({key: value for key, value in item.items() if key != "name"})
			item["name"] = section.name
		frappe.db.set_value("Workspace Sidebar Item", item.name,
			{key: item[key] for key in ("idx", "child", "collapsible", "keep_closed") if key in item},
			update_modified=False)
	retained = {item.name for item in sidebar["items"]}
	for item in _get_items():
		if item.type in {"Section Break", "Card Break", "Sidebar Item Group"} and item.name not in retained:
			frappe.db.delete("Workspace Sidebar Item", {"name": item.name})
	frappe.clear_cache()


def _get_items():
	return frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": SIDEBAR_NAME},
		fields=["name", "idx", "label", "type", "link_type", "link_to"],
		order_by="idx, creation",
	)


def _ensure_link(items, *, link_type, link_to, label, icon, child):
	item = next(
		(item for item in items if item.type == "Link" and item.link_type == link_type and item.link_to == link_to),
		None,
	)
	if not item:
		item = _create_item(
			{
				"label": label,
				"type": "Link",
				"link_type": link_type,
				"link_to": link_to,
				"icon": icon,
				"child": child,
			}
		)
		items.append(item)
	else:
		frappe.db.set_value(
			"Workspace Sidebar Item",
			item.name,
			{"label": label, "icon": icon, "child": child},
			update_modified=False,
		)
		item.label = label
	return item


def _create_item(values):
	item = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar Item",
			"parent": SIDEBAR_NAME,
			"parenttype": "Workspace Sidebar",
			"parentfield": "items",
			"idx": 9999,
			"collapsible": 1,
			"indent": 0,
			"keep_closed": 0,
			"show_arrow": 0,
			**values,
		}
	)
	item.insert(ignore_permissions=True)
	return frappe._dict(
		{
			"name": item.name,
			"idx": item.idx,
			"label": item.label,
			"type": item.type,
			"link_type": item.link_type,
			"link_to": item.link_to,
		}
	)


def _find_section(items, labels):
	return next((item for item in items if item.type == "Section Break" and item.label in labels), None)


def _move_after(items, item_name, anchor_link_to):
	target = next(item for item in items if item.name == item_name)
	ordered = [item for item in items if item.name != item_name]
	anchor_index = next(
		(index for index, item in enumerate(ordered) if item.type == "Link" and item.link_to == anchor_link_to),
		None,
	)
	if anchor_index is None:
		return items
	ordered.insert(anchor_index + 1, target)
	return ordered


def _place_after(items, item_names, anchor_name):
	by_name = {item.name: item for item in items}
	ordered = [item for item in items if item.name not in item_names]
	anchor_index = next(index for index, item in enumerate(ordered) if item.name == anchor_name)
	ordered[anchor_index + 1 : anchor_index + 1] = [by_name[name] for name in item_names]
	return ordered


def _reindex(items):
	for idx, item in enumerate(items, start=1):
		frappe.db.set_value("Workspace Sidebar Item", item.name, "idx", idx, update_modified=False)
