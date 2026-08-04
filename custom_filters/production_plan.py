import frappe
from frappe.utils import flt

from erpnext.manufacturing.doctype.production_plan.production_plan import (
	get_bin_details,
	get_items_for_material_requests as erpnext_get_items_for_material_requests,
)


@frappe.whitelist()
def get_items_for_material_requests(
	doc, warehouses=None, get_parent_warehouse_data=None, warehouse_selection_mode=None
):
	"""Keep ERPNext calculations and choose one receiving warehouse per item.

	The same item can have both Purchase and Material Transfer rows. They must
	use one destination warehouse, otherwise the purchase and transfer flows
	will replenish different locations. For the combined purchase/transfer
	operation, priority is: Item Default, ERPNext's existing Purchase
	destination, then the warehouse with the highest positive actual stock
	(excluding the company's WIP warehouse). The purchase-only operation puts
	the highest-stock warehouse ahead of ERPNext's proposed destination.
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

	company_warehouses = set(
		frappe.get_all(
			"Warehouse",
			filters={"company": company, "is_group": 0, "disabled": 0},
			pluck="name",
		)
	)
	default_warehouse_by_item = {
		item_code: warehouse
		for item_code, warehouse in warehouse_by_item.items()
		if warehouse in company_warehouses
	}
	# ERPNext's Purchase row carries the intended receiving warehouse. When an
	# Item Default is absent, prefer that stable destination over selecting a
	# warehouse separately for each generated row.
	purchase_warehouse_by_item = {}
	for row in items:
		item_code = row.get("item_code")
		warehouse = row.get("warehouse")
		if (
			item_code
			and row.get("material_request_type") != "Material Transfer"
			and warehouse in company_warehouses
			and item_code not in purchase_warehouse_by_item
		):
			purchase_warehouse_by_item[item_code] = warehouse

	target_warehouse_by_item = {}
	for item_code in item_codes:
		if warehouse_selection_mode == "purchase_only":
			target_warehouse_by_item[item_code] = (
				default_warehouse_by_item.get(item_code)
				or stock_warehouse_by_item.get(item_code)
				or purchase_warehouse_by_item.get(item_code)
			)
		else:
			target_warehouse_by_item[item_code] = (
				default_warehouse_by_item.get(item_code)
				or purchase_warehouse_by_item.get(item_code)
				or stock_warehouse_by_item.get(item_code)
			)

	for row in items:
		item_code = row.get("item_code")
		row["custom_transfer_qty"] = (
			flt(row.get("quantity"))
			if row.get("material_request_type") == "Material Transfer"
			else 0
		)
		warehouse = target_warehouse_by_item.get(item_code)
		if warehouse:
			# ERPNext uses `warehouse` as the receiving warehouse for Material
			# Transfer rows. Apply the Item Default consistently for both Purchase
			# and Material Transfer; keep `from_warehouse` intact so the native
			# transfer source selected from available stock is not lost.
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
