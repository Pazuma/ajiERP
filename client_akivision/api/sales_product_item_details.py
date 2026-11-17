"""Preserve ERPNext item calculations while excluding costs for sales-only users."""

import frappe
from frappe import _

from client_akivision.utils.item_product_identity import _sales_only_user


@frappe.whitelist()
def get_item_details(ctx, doc=None, for_validate=False, overwrite_warehouse=True):
	from erpnext.stock.get_item_details import get_item_details as native_get_item_details
	if not _sales_only_user():
		return native_get_item_details(ctx, doc, for_validate, overwrite_warehouse)
	values = frappe.parse_json(ctx) if isinstance(ctx, str) else ctx
	if values.get("doctype") not in ("Sales Order", "Quotation", "Delivery Note", "Sales Invoice"):
		frappe.throw(_("销售账号只能查询销售单据的物料信息。"), frappe.PermissionError)
	frappe.has_permission("Item", "read", doc=values.get("item_code"), throw=True)
	warehouse = values.get("warehouse") or values.get("set_warehouse")
	if warehouse:
		frappe.has_permission("Warehouse", "read", doc=warehouse, throw=True)
	price_list = values.get("selling_price_list") or values.get("price_list")
	if price_list and not frappe.db.exists("Price List", {"name": price_list, "enabled": 1, "selling": 1, "buying": 0}):
		frappe.throw(_("只能使用已启用的纯销售价目表。"), frappe.PermissionError)
	result = native_get_item_details(ctx, doc, for_validate, overwrite_warehouse)
	for field in ("valuation_rate", "last_purchase_rate", "buying_price_list", "stock_value", "gross_profit"):
		result.pop(field, None)
	result.pop("company_total_stock", None)
	result_warehouse = result.get("warehouse")
	if result_warehouse:
		frappe.has_permission("Warehouse", "read", doc=result_warehouse, throw=True)
		quantities = get_bin_details(values.get("item_code"), result_warehouse, include_child_warehouses=True)
		for field, quantity in quantities.items():
			if field in result:
				result[field] = quantity
	return result


@frappe.whitelist()
def get_valuation_rate(item_code, company, warehouse=None):
	if _sales_only_user():
		frappe.throw(_("销售账号无权查询库存估值。"), frappe.PermissionError)
	from erpnext.stock.get_item_details import get_valuation_rate as native_get_valuation_rate
	return native_get_valuation_rate(item_code, company, warehouse)


@frappe.whitelist()
def get_item_master_details(item_code, company=None):
	from erpnext.stock.doctype.item.item import get_item_details as native_get_item_master_details
	if not _sales_only_user():
		return native_get_item_master_details(item_code, company)
	frappe.has_permission("Item", "read", doc=item_code, throw=True)
	result = native_get_item_master_details(item_code, company)
	from frappe.model import get_permitted_fields
	return {key: value for key, value in result.items() if key in get_permitted_fields("Item")}


@frappe.whitelist()
def get_stock_balance(item_code, warehouse, posting_date=None, posting_time=None,
		with_valuation_rate=False, with_serial_no=False, inventory_dimensions_dict=None):
	from erpnext.stock.utils import get_stock_balance as native_get_stock_balance
	if _sales_only_user():
		frappe.has_permission("Item", "read", doc=item_code, throw=True)
		frappe.has_permission("Warehouse", "read", doc=warehouse, throw=True)
		if frappe.utils.cint(with_valuation_rate):
			frappe.throw(_("销售账号无权查询库存估值。"), frappe.PermissionError)
	return native_get_stock_balance(item_code, warehouse, posting_date, posting_time,
		with_valuation_rate, with_serial_no, inventory_dimensions_dict)


@frappe.whitelist()
def get_bin_details(item_code, warehouse, company=None, include_child_warehouses=False):
	from erpnext.stock.get_item_details import get_bin_details as native_get_bin_details
	if not _sales_only_user():
		return native_get_bin_details(item_code, warehouse, company, include_child_warehouses)
	frappe.has_permission("Item", "read", doc=item_code, throw=True)
	result = {"actual_qty": 0, "reserved_qty": 0, "projected_qty": 0}
	if not warehouse:
		return result
	frappe.has_permission("Warehouse", "read", doc=warehouse, throw=True)
	from client_akivision.client_akivision.api.item_list import get_item_list_stock_context
	context = get_item_list_stock_context([item_code], include_zero_qty=1, view="sales_product")
	warehouses = {warehouse}
	if frappe.utils.cint(include_child_warehouses):
		from erpnext.stock.doctype.warehouse.warehouse import get_child_warehouses
		warehouses.update(get_child_warehouses(warehouse))
	for row in context["items"].get(item_code, {}).get("warehouses", []):
		if row["warehouse"] in warehouses:
			for field in result:
				result[field] += row[field]
	return result


@frappe.whitelist()
def get_projected_qty(item_code, warehouse):
	if _sales_only_user():
		return {"projected_qty": get_bin_details(item_code, warehouse)["projected_qty"]}
	from erpnext.stock.get_item_details import get_projected_qty as native_get_projected_qty
	return native_get_projected_qty(item_code, warehouse)


@frappe.whitelist()
def apply_price_list(ctx, as_doc=False, doc=None):
	from erpnext.stock.get_item_details import apply_price_list as native_apply_price_list
	if _sales_only_user():
		values = frappe.parse_json(ctx) if isinstance(ctx, str) else ctx
		if values.get("doctype") not in ("Sales Order", "Quotation", "Delivery Note", "Sales Invoice"):
			frappe.throw(_("销售账号只能使用销售单据定价。"), frappe.PermissionError)
		for field in ("price_list", "selling_price_list", "buying_price_list"):
			name = values.get(field)
			if name and not frappe.db.exists("Price List", {"name": name, "enabled": 1, "selling": 1, "buying": 0}):
				frappe.throw(_("只能使用已启用的纯销售价目表。"), frappe.PermissionError)
		for row in values.get("items") or []:
			frappe.has_permission("Item", "read", doc=row.get("item_code"), throw=True)
	return native_apply_price_list(ctx, as_doc, doc)
