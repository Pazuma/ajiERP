import frappe
from frappe.utils import flt

from erpnext.manufacturing.doctype.production_plan.production_plan import (
	get_bin_details,
	get_items_for_material_requests as erpnext_get_items_for_material_requests,
)


@frappe.whitelist()
def get_items_for_material_requests(doc, warehouses=None, get_parent_warehouse_data=None):
	"""Keep ERPNext calculations and choose each raw material's best warehouse.

	Priority is: Item Default, the warehouse with the highest positive actual
	stock (excluding the company's WIP warehouse), then ERPNext's original
	warehouse value.
	"""
	items = erpnext_get_items_for_material_requests(doc, warehouses, get_parent_warehouse_data)
	if not items:
		return items

	if isinstance(doc, str):
		doc = frappe.parse_json(doc)
	company = doc.get("company")
	if not company:
		return items

	item_codes = {row.get("item_code") for row in items if row.get("item_code")}
	if not item_codes:
		return items

	defaults = frappe.get_all(
		"Item Default",
		filters={"parent": ["in", list(item_codes)], "company": company},
		fields=["parent", "default_warehouse"],
	)
	warehouse_by_item = {
		row.parent: row.default_warehouse
		for row in defaults
		if row.default_warehouse
	}
	
	# The WIP warehouse is a production staging location, not a stock source
	# for this selection. Read all bins in one query to avoid one query per row.
	wip_warehouse = frappe.db.get_value("Company", company, "default_wip_warehouse")
	stock_rows = frappe.get_all(
		"Bin",
		filters={
			"item_code": ["in", list(item_codes)],
			"warehouse.company": company,
			"warehouse.is_group": 0,
			**({"warehouse": ["!=", wip_warehouse]} if wip_warehouse else {}),
		},
		fields=["item_code", "warehouse", "actual_qty"],
		order_by="actual_qty desc",
	)
	stock_warehouse_by_item = {}
	for stock_row in stock_rows:
		if flt(stock_row.actual_qty) > 0 and stock_row.item_code not in stock_warehouse_by_item:
			stock_warehouse_by_item[stock_row.item_code] = stock_row.warehouse

	valid_warehouses = set(
		frappe.get_all(
			"Warehouse",
			filters={"name": ["in", list(warehouse_by_item.values())], "company": company},
			pluck="name",
		)
	)

	for row in items:
		item_code = row.get("item_code")
		row["custom_transfer_qty"] = (
			flt(row.get("quantity"))
			if row.get("material_request_type") == "Material Transfer"
			else 0
		)
		# ERPNext uses `warehouse` as the destination and `from_warehouse`
		# as the source for transfer rows. Do not rewrite the destination after
		# the native allocation, otherwise a valid transfer can be recreated
		# even when the destination already has stock.
		if row.get("material_request_type") == "Material Transfer":
			continue

		warehouse = warehouse_by_item.get(item_code)
		if warehouse not in valid_warehouses:
			warehouse = stock_warehouse_by_item.get(item_code)
		if warehouse:
			row["warehouse"] = warehouse
			_refresh_row_stock_values(row, company, warehouse, doc.get("ignore_existing_ordered_qty"))

	return items


def _refresh_row_stock_values(row, company, warehouse, ignore_existing_ordered_qty):
	"""Refresh stock values and recalculate demand when projected stock is enabled."""
	bin_rows = get_bin_details(row, company, for_warehouse=warehouse)
	stock = bin_rows[0] if bin_rows else {}
	for fieldname in ("actual_qty", "projected_qty", "ordered_qty", "reserved_qty_for_production"):
		row[fieldname] = stock.get(fieldname, 0)

	if ignore_existing_ordered_qty and row.get("required_bom_qty") is not None:
		available_qty = max(flt(row.get("projected_qty")), 0)
		required_qty = max(flt(row.get("required_bom_qty")) - available_qty, 0)
		conversion_factor = flt(row.get("conversion_factor")) or 1
		row["quantity"] = required_qty / conversion_factor
