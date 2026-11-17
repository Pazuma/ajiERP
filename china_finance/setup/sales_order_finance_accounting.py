"""Idempotent, sales-order-only finance field isolation."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import add_permission, update_permission_property

from china_finance.services.sales_order_finance_permissions import READER_ROLES, EDITOR_ROLES

FINANCE_LEVEL = 8
ORDER_FIELDS = (
	"custom_material_cost", "custom_auxiliary_material_cost", "custom_labor_cost",
	"custom_manufacturing_overhead", "custom_normal_loss_cost", "custom_abnormal_loss_cost",
	"custom_scrap_recovery", "custom_production_cost", "custom_delivered_cost",
	"custom_recognized_revenue", "custom_gross_profit", "custom_gross_margin",
	"custom_production_cost_section", "custom_cost_column", "custom_cost_last_updated",
	"custom_order_loss_rate", "custom_enable_production_cost", "custom_cost_end_column",
)


def ensure_schema():
	for role in ("Sales Order Finance Reader", "Sales Order Finance Editor"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc(dict(doctype="Role", role_name=role)).insert(ignore_permissions=True)
	for doctype, fields in (("Sales Order", ORDER_FIELDS), ("Sales Order Item", ("valuation_rate", "gross_profit"))):
		meta = frappe.get_meta(doctype)
		occupied = [df.fieldname for df in meta.fields if df.permlevel == FINANCE_LEVEL and df.fieldname not in fields]
		if occupied:
			frappe.throw(f"{doctype} 权限层级 {FINANCE_LEVEL} 已被其他字段使用：{', '.join(occupied)}；请先指定独立层级。")
		for field in fields:
			if meta.has_field(field) and meta.get_field(field).permlevel != FINANCE_LEVEL:
				make_property_setter(doctype, field, "permlevel", FINANCE_LEVEL, "Int", validate_fields_for_doctype=False)
		# Level 8 is reserved for this capability. Remove obsolete finance-level grants.
		for permission in frappe.get_all("Custom DocPerm", filters={"parent": doctype, "permlevel": FINANCE_LEVEL}, fields=["name", "role"]):
			if permission.role not in READER_ROLES:
				frappe.delete_doc("Custom DocPerm", permission.name, ignore_permissions=True)
		for role in READER_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": FINANCE_LEVEL}):
				add_permission(doctype, role, FINANCE_LEVEL)
			update_permission_property(doctype, role, FINANCE_LEVEL, "read", 1, validate=False)
			update_permission_property(doctype, role, FINANCE_LEVEL, "write", int(role in EDITOR_ROLES), validate=False)
		frappe.clear_cache(doctype=doctype)
