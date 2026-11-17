"""Field-level cost isolation for the standard product and sales order forms."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import add_permission, update_permission_property

from client_akivision.utils.sales_order_production_cost import SO_COST_FIELDS


COST_LEVEL = 9
COST_ROLES = ("System Manager", "Accounts User", "Accounts Manager", "Stock User", "Stock Manager",
	"Purchase User", "Purchase Manager", "Manufacturing User", "Manufacturing Manager")
FINANCE_ROLES = ("System Manager", "Accounts User", "Accounts Manager", "China Finance User", "China Finance Manager", "China Finance Auditor", "Sales Order Finance Reader", "Sales Order Finance Editor")
FIELDS = {
	"Item": ("valuation_rate", "last_purchase_rate", "standard_rate", "valuation_method",
		"inventory_valuation_section", "purchasing_tab", "supplier_items", "custom_purchase_average_cost_html"),
	"Bin": ("valuation_rate", "stock_value"),
	"Sales Order": (*SO_COST_FIELDS, "custom_production_cost_section", "custom_cost_column", "custom_cost_last_updated"),
	"Sales Order Item": ("valuation_rate", "gross_profit"),
}


def ensure_schema():
	for doctype, fields in FIELDS.items():
		is_order = doctype in ("Sales Order", "Sales Order Item")
		level = 8 if is_order else COST_LEVEL
		if doctype == "Sales Order":
			fields = (*fields, "custom_order_loss_rate", "custom_enable_production_cost", "custom_cost_end_column")
		meta = frappe.get_meta(doctype)
		for field in fields:
			if meta.has_field(field):
				if meta.get_field(field).permlevel != level:
					make_property_setter(doctype, field, "permlevel", level, "Int", validate_fields_for_doctype=False)
		for role in FINANCE_ROLES if is_order else COST_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			# Do not grant a role any new DocType-level access.
			base = frappe.get_all("Custom DocPerm", filters={"parent": doctype, "role": role, "permlevel": 0}, fields=["read", "write"])
			if not base:
				base = frappe.get_all("DocPerm", filters={"parent": doctype, "role": role, "permlevel": 0}, fields=["read", "write"])
			# System Manager has implicit base access and may have no level-0 row.
			if role != "System Manager" and (not base or not base[0].read):
				continue
			if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": level}):
				add_permission(doctype, role, level)
			update_permission_property(doctype, role, level, "read", 1, validate=False)
			# System Manager must retain write access to restricted fields even when
			# an older/custom level-0 Item permission was read-only at migration time.
			# Otherwise the form renders supplier_items read-only and hides Add Row.
			write = 1 if role == "System Manager" else base[0].write
			update_permission_property(doctype, role, level, "write", write, validate=False)
		frappe.clear_cache(doctype=doctype)
