"""Shared scope and stock-balance helpers for department inventory reports."""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.stock.report.stock_balance.stock_balance import execute as execute_stock_balance


def get_configured_list(key):
	value = frappe.conf.get(key)
	if not value:
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			value = value.split(",")
	return [str(item).strip() for item in value if str(item).strip()]


def get_allowed_warehouses(config_key, company=None):
	configured = get_configured_list(config_key)
	if not configured:
		return []
	existing = set(frappe.get_all("Warehouse", filters={"name": ["in", configured], **({"company": company} if company else {})}, pluck="name"))
	configured = [warehouse for warehouse in configured if warehouse in existing]
	if frappe.session.user == "Administrator":
		return configured
	permissions = frappe.get_user_permissions().get("Warehouse", [])
	if not permissions:
		return [warehouse for warehouse in configured if frappe.has_permission("Warehouse", "read", warehouse)]
	permitted_names = {row.get("doc") for row in permissions}
	return [warehouse for warehouse in configured if warehouse in permitted_names and frappe.has_permission("Warehouse", "read", warehouse)]


def require_scope(config_key, company=None):
	if not get_configured_list(config_key):
		return []
	warehouses = get_allowed_warehouses(config_key, company)
	if not warehouses:
		frappe.throw(_("您没有查看已配置仓库的权限"), frappe.PermissionError)
	return warehouses


def get_stock_rows(warehouses, company, item_group=None):
	rows = []
	for warehouse in warehouses:
		_, warehouse_rows = execute_stock_balance(frappe._dict({
			"company": company, "from_date": nowdate(), "to_date": nowdate(), "item_group": item_group,
			"warehouse": [warehouse], "ignore_closing_balance": 0, "include_zero_stock_items": 0,
			"show_stock_ageing_data": 0, "show_variant_attributes": 0, "show_alt_uom_balance": 0,
			"show_warehouse_wise_stock": 1,
		}))
		rows.extend(warehouse_rows)
	return rows


def format_stock_rows(rows):
	if not rows:
		return []
	rows_by_key = {(row.item_code, row.warehouse): row for row in rows}
	rows = list(rows_by_key.values())
	item_codes = list({row.item_code for row in rows})
	warehouses = list({row.warehouse for row in rows})
	bins = frappe.get_all(
		"Bin",
		filters={"item_code": ["in", item_codes], "warehouse": ["in", warehouses]},
		fields=["item_code", "warehouse", "projected_qty"],
	)
	projected = {(row.item_code, row.warehouse): flt(row.projected_qty) for row in bins}
	return [
		{
			"item_code": row.item_code,
			"item_name": row.item_name,
			"item_group": row.item_group,
			"actual_qty": flt(row.bal_qty),
			"projected_qty": projected.get((row.item_code, row.warehouse), flt(row.bal_qty)),
			"stock_uom": row.stock_uom,
			"warehouse": row.warehouse,
		}
		for row in rows
	]
