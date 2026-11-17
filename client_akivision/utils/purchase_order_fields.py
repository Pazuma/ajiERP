"""Purchase Order defaults and ownership validation for individual buyers."""

import frappe
from frappe import _
import json

from client_akivision.utils.order_record_permissions import get_current_employee, is_scoped_user


def ensure_schema():
	"""Create the procurement specialist field and sync PO section behavior."""
	path = frappe.get_app_path("client_akivision", "config", "excel_form_fields.json")
	with open(path, encoding="utf-8") as source:
		registry = json.load(source)
	fields = [
		field
		for field in registry.get("custom_fields", {}).get("Purchase Order", [])
		if field.get("fieldname") == "custom_procurement_specialist"
	]
	if not fields:
		frappe.throw(_("采购专员字段未在自定义字段配置中声明。"))
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({"Purchase Order": fields}, update=True)
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter
	make_property_setter(
		"Purchase Order", "taxes_section", "collapsible", 1, "Check", is_system_generated=True
	)
	make_property_setter(
		"Purchase Order", "section_break_52", "collapsible", 0, "Check", is_system_generated=True
	)
	make_property_setter(
		"Purchase Order", "totals_section", "collapsible", 1, "Check", is_system_generated=True
	)
	_ensure_header_field_layout(make_property_setter)
	_ensure_tax_section_layout(make_property_setter)
	frappe.db.updatedb("Purchase Order")
	frappe.clear_cache(doctype="Purchase Order")


def _ensure_header_field_layout(make_property_setter=None):
	"""Arrange purchase-order header fields in three columns and group checks."""
	if not frappe.db.exists("DocType", "Purchase Order"):
		return
	if make_property_setter is None:
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	field_order = [field.fieldname for field in frappe.get_meta("Purchase Order").fields]
	required = {
		"supplier_section", "naming_series", "supplier", "transaction_date", "company",
		"schedule_date", "is_subcontracted", "custom_supplier_consolidation",
		"custom_excel_category", "custom_excel_order_no", "custom_excel_import_status",
		"custom_procurement_specialist", "supplier_name", "order_confirmation_no",
		"order_confirmation_date", "column_break_7", "column_break1",
	}
	if not required.issubset(field_order):
		return

	# Build three balanced columns from the visible header, then retain remaining fields.
	for fieldname in (
		"naming_series", "supplier", "supplier_name", "order_confirmation_no",
		"order_confirmation_date", "column_break_7", "transaction_date", "schedule_date",
		"column_break1", "company", "is_subcontracted", "custom_supplier_consolidation",
		"custom_excel_category", "custom_excel_order_no", "custom_excel_import_status",
		"custom_procurement_specialist",
	):
		field_order.remove(fieldname)

	start = field_order.index("supplier_section") + 1
	field_order[start:start] = [
		"naming_series", "supplier", "custom_excel_order_no", "custom_supplier_consolidation",
		"column_break_7", "transaction_date", "schedule_date", "custom_excel_import_status",
		"column_break1", "company", "custom_excel_category", "custom_procurement_specialist",
		"is_subcontracted", "supplier_name", "order_confirmation_no", "order_confirmation_date",
	]
	value = json.dumps(field_order, ensure_ascii=False)
	existing = frappe.db.get_value(
		"Property Setter",
		{"doctype_or_field": "DocType", "doc_type": "Purchase Order", "property": "field_order"},
		"value",
	)
	if existing != value:
		make_property_setter(
			"Purchase Order", None, "field_order", value, "JSON", for_doctype=True, is_system_generated=True
		)


def _ensure_tax_section_layout(make_property_setter=None):
	"""Arrange tax template, charge rows, and tax total in a compact two-column layout."""
	if not frappe.db.exists("DocType", "Purchase Order"):
		return
	if make_property_setter is None:
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	field_order = [field.fieldname for field in frappe.get_meta("Purchase Order").fields]
	required = {
		"taxes_section",
		"taxes_and_charges",
		"column_break_50",
		"shipping_rule",
		"section_break_52",
		"taxes",
		"column_break_53",
		"totals",
		"totals_section",
		"total_taxes_and_charges",
	}
	if not required.issubset(field_order):
		return
	# Put total tax beside the template, and keep the taxes table below the
	# template fields. The separate totals section remains independently collapsible.
	for fieldname in ("section_break_52", "taxes", "total_taxes_and_charges"):
		field_order.remove(fieldname)
	template_index = field_order.index("taxes_and_charges")
	column_break_index = field_order.index("column_break_53")
	if column_break_index < template_index:
		return
	field_order.insert(column_break_index + 1, "total_taxes_and_charges")
	insert_at = field_order.index("totals")
	field_order[insert_at:insert_at] = ["section_break_52", "taxes"]
	value = json.dumps(field_order, ensure_ascii=False)
	existing = frappe.db.get_value(
		"Property Setter",
		{"doctype_or_field": "DocType", "doc_type": "Purchase Order", "property": "field_order"},
		"value",
	)
	if existing != value:
		make_property_setter(
			"Purchase Order", None, "field_order", value, "JSON", for_doctype=True, is_system_generated=True
		)


@frappe.whitelist()
def get_current_user_procurement_specialist():
	"""Return the logged-in Purchase User's active Employee record."""
	if not is_scoped_user("Purchase Order"):
		return None
	employee = get_current_employee()
	if not employee:
		frappe.throw(_("当前账号没有唯一有效的员工关联，请联系管理员维护 Employee。"))
	return employee


def set_and_validate_procurement_specialist(doc, method=None):
	"""Assign new POs to their creating Purchase User and prevent reassignment."""
	if doc.doctype != "Purchase Order" or not is_scoped_user("Purchase Order"):
		return

	if not doc.meta.has_field("custom_procurement_specialist"):
		frappe.throw(_("采购专员字段尚未安装，请先运行站点迁移。"))

	employee = get_current_employee()
	if not employee:
		frappe.throw(_("当前账号没有唯一有效的员工关联，请联系管理员维护 Employee。"))

	if doc.is_new():
		doc.custom_procurement_specialist = employee
		return

	stored_employee = frappe.db.get_value("Purchase Order", doc.name, "custom_procurement_specialist")
	if stored_employee != employee:
		frappe.throw(_("您只能修改分配给自己的采购订单。"), frappe.PermissionError)
	if doc.custom_procurement_specialist != stored_employee:
		frappe.throw(_("普通采购人员不能变更采购订单负责人。"), frappe.PermissionError)
