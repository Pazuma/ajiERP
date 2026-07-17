"""Synchronize client_akivision links into Workspace Sidebar sections."""

import frappe


SIDEBAR_LINKS = {
	"Selling": {
		"reports": (
			("Report", "Delivery List", "送货清单", "delivery_list"),
			("Report", "Sales Order List", "销售订单清单", "sales_order_list"),
		),
	},
	"Buying": {
		"reports": (
			("Report", "Purchase List", "采购清单", "purchase_list"),
			("Report", "Supplier Performance Evaluation", "供应商回顾", "supplier_performance_evaluation"),
			("Report", "Purchase Delay Analysis", "采购到货延迟分析", "purchase_delay_analysis"),
		),
	},
	"Stock": {
		"records": (
			("DocType", "Sample Loan Out", "借出样品"),
			("DocType", "Sample Loan Out Return", "借出归还"),
			("DocType", "Sample Loan In", "借入样品"),
			("DocType", "Sample Loan In Return", "借入归还"),
			("DocType", "Finished Goods Status", "成品状态"),
		),
		"reports": (
			("Report", "Receipt List", "入库清单", "receipt_list"),
			("Report", "Outbound List", "出库清单", "outbound_list"),
			("Report", "Realtime Inventory", "实时库存", "realtime_inventory"),
			("Report", "Safety Stock Status", "安全库存状态", "safety_stock_status"),
			("Report", "Sample Loan Out List", "借出样品清单", "sample_loan_out_list"),
			("Report", "Sample Loan In List", "借回样品清单", "sample_loan_in_list"),
			("Report", "Finished Goods Status", "成品状态", "finished_goods_status"),
			("Report", "Summary Calculation", "汇总计算", "summary_calculation"),
		),
	},
	"Financial Reports": {
		"reports": (
			("Report", "Receivable Aging Analysis", "应收账龄分析", "receivable_aging_analysis"),
		),
	},
	"Payments": {
		"records": (
			("DocType", "Payment Entry", "Payment Entry"),
		),
		"reports": (
			("Report", "Receipt Record", "回款记录", "receipt_record"),
			("Report", "Purchase Payment Record", "付款记录", "purchase_payment_record"),
		),
	},
	"Projects": {
		"reports": (
			("Report", "RD Project List", "研发项目清单", "rd_project_list"),
		),
	},
	"Manufacturing": {
		"records": (
			("DocType", "Engineering Drawing", "工程图纸"),
		),
	},
}

HIDDEN_SIDEBAR_LINKS = {
	"Selling": {("Report", "High-tech Revenue Analysis")},
}

SECTION_DEFS = {
	"records": {"labels": {"Records", "记录", "Tools", "工具"}, "label": "Records", "icon": "folder"},
	"reports": {"labels": {"Reports", "报表"}, "label": "Reports", "icon": "sheet"},
}


def sync_report_sidebar_entries():
	"""Restore report and custom DocType sidebar links after every migrate."""
	for sidebar_name, links in HIDDEN_SIDEBAR_LINKS.items():
		_remove_links(sidebar_name, links)

	for sidebar_name, sections in SIDEBAR_LINKS.items():
		if not frappe.db.exists("Workspace Sidebar", sidebar_name):
			continue
		for section_key, links in sections.items():
			_sync_section(sidebar_name, section_key, links)

	frappe.cache.delete_key("bootinfo")
	frappe.clear_cache()


def _remove_links(sidebar_name, targets):
	items = _get_items(sidebar_name)
	for item in items:
		if (item.link_type, item.link_to) in targets:
			frappe.delete_doc("Workspace Sidebar Item", item.name, force=True, ignore_permissions=True)

	_reindex(_get_items(sidebar_name))


def _sync_section(sidebar_name, section_key, links):
	for link in links:
		if link[0] == "Report":
			frappe.reload_doc("client_akivision", "report", link[3], force=True)

	items = _get_items(sidebar_name)
	section = _find_section(items, SECTION_DEFS[section_key]["labels"])
	if not section:
		section = _create_item(
			sidebar_name,
			{
				"label": SECTION_DEFS[section_key]["label"],
				"type": "Section Break",
				"icon": SECTION_DEFS[section_key]["icon"],
				"child": 0,
			},
		)
		items.append(section)

	targets = {(link_type, link_to) for link_type, link_to, *_ in links}
	for item in items:
		if (item.link_type, item.link_to) in targets:
			frappe.delete_doc("Workspace Sidebar Item", item.name, force=True, ignore_permissions=True)

	items = [item for item in _get_items(sidebar_name) if (item.link_type, item.link_to) not in targets]
	section = _find_section(items, SECTION_DEFS[section_key]["labels"])
	link_items = [
		_create_item(
			sidebar_name,
			{
				"label": label,
				"type": "Link",
				"link_type": link_type,
				"link_to": link_to,
				"child": 1,
				**_optional_link_values(link_type),
			},
		)
		for link_type, link_to, label, *_ in links
	]
	items.extend(link_items)
	items = _place_after(items, [item.name for item in link_items], section.name)
	_reindex(items)


def _optional_link_values(link_type):
	values = {}
	meta = frappe.get_meta("Workspace Sidebar Item")
	if link_type == "Report" and meta.has_field("is_query_report"):
		values["is_query_report"] = 1
	return values


def _get_items(sidebar_name):
	return frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parent": sidebar_name},
		fields=["name", "idx", "label", "type", "link_type", "link_to"],
		order_by="idx, creation",
	)


def _find_section(items, labels):
	section_types = {"Section Break", "Card Break", "Sidebar Item Group"}
	return next((item for item in items if item.type in section_types and item.label in labels), None)


def _create_item(sidebar_name, values):
	item = frappe.get_doc(
		{
			"doctype": "Workspace Sidebar Item",
			"parent": sidebar_name,
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


def _place_after(items, item_names, anchor_name):
	by_name = {item.name: item for item in items}
	ordered = [item for item in items if item.name not in item_names]
	anchor_index = next(index for index, item in enumerate(ordered) if item.name == anchor_name)
	ordered[anchor_index + 1 : anchor_index + 1] = [by_name[name] for name in item_names]
	return ordered


def _reindex(items):
	for idx, item in enumerate(items, start=1):
		frappe.db.set_value("Workspace Sidebar Item", item.name, "idx", idx, update_modified=False)
