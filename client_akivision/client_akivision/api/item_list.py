import frappe
from frappe import _
from frappe.utils import cint, flt


MAX_ITEM_CODES = 100


def _parse_item_codes(item_codes):
	parsed = frappe.parse_json(item_codes or [])
	if not isinstance(parsed, list):
		frappe.throw(_("item_codes must be a list."))
	codes = list(dict.fromkeys(str(code).strip() for code in parsed if str(code).strip()))
	if len(codes) > MAX_ITEM_CODES:
		frappe.throw(_("A maximum of {0} items can be requested.").format(MAX_ITEM_CODES))
	return codes


@frappe.whitelist()
def get_item_list_stock_context(item_codes=None, warehouse=None, include_zero_qty=0, view=None):
	"""Return read-only warehouse stock and reorder context for Item List rows."""
	if view == "sales_product":
		roles = set(frappe.get_roles(frappe.session.user))
		if not roles.intersection({"Sales User", "Sales Manager", "System Manager"}):
			frappe.throw(_("仅销售角色可访问销售产品库存视图。"), frappe.PermissionError)
	item_codes = _parse_item_codes(item_codes)
	if not item_codes:
		return {"items": {}}
	for doctype in (("Item", "Bin", "Warehouse") if view == "sales_product" else ("Item", "Bin", "Item Reorder", "Warehouse")):
		if not frappe.has_permission(doctype, "read"):
			frappe.throw(_("You do not have permission to read {0}.").format(doctype), frappe.PermissionError)

	item_filters = {"name": ["in", item_codes]}
	if view == "sales_product":
		item_filters.update({"is_sales_item": 1, "disabled": 0})
	item_rows = frappe.get_list(
		"Item",
		filters=item_filters,
		fields=["name", "stock_uom"],
		limit_page_length=MAX_ITEM_CODES,
	)
	allowed_codes = {row.name for row in item_rows}
	if not allowed_codes:
		return {"items": {}}
	allowed_warehouses = set(frappe.get_list("Warehouse", pluck="name", limit_page_length=0))
	if warehouse and warehouse not in allowed_warehouses:
		frappe.throw(_("You do not have permission to read this warehouse."), frappe.PermissionError)
	if not allowed_warehouses:
		return {"items": {row.name: {"stock_uom": row.stock_uom, "warehouses": [], "reorder_levels": []} for row in item_rows}, "warehouse": warehouse}

	bin_filters = {"item_code": ["in", list(allowed_codes)], "warehouse": ["in", list(allowed_warehouses)]}
	if warehouse:
		bin_filters["warehouse"] = warehouse
	if not cint(include_zero_qty):
		bin_filters["actual_qty"] = ["!=", 0]
	bin_rows = frappe.get_list(
		"Bin",
		filters=bin_filters,
		fields=["item_code", "warehouse", "actual_qty", "reserved_qty", "projected_qty"],
		order_by="item_code asc, warehouse asc",
		limit_page_length=0,
	)

	reorder_filters = {"parent": ["in", list(allowed_codes)], "warehouse": ["in", list(allowed_warehouses)]}
	if warehouse:
		reorder_filters["warehouse"] = warehouse
	reorder_rows = [] if view == "sales_product" else frappe.get_list(
		"Item Reorder",
		filters=reorder_filters,
		fields=["parent as item_code", "warehouse", "warehouse_reorder_level"],
		order_by="parent asc, idx asc",
		parent_doctype="Item",
		limit_page_length=0,
	)

	result = {
		row.name: {"stock_uom": row.stock_uom, "warehouses": [], "reorder_levels": []}
		for row in item_rows
	}
	for row in bin_rows:
		result[row.item_code]["warehouses"].append(
			{"warehouse": row.warehouse, "actual_qty": flt(row.actual_qty),
			 "reserved_qty": flt(row.reserved_qty), "projected_qty": flt(row.projected_qty)}
		)
	for row in reorder_rows:
		result[row.item_code]["reorder_levels"].append(
			{"warehouse": row.warehouse, "warehouse_reorder_level": flt(row.warehouse_reorder_level)}
		)

	return {"items": result, "warehouse": warehouse}
