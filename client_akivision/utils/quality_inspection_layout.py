"""Presentation-only quality inspection grouping; preserve all business fields."""
import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def ensure_layout():
	dt = "Quality Inspection"
	options = frappe.get_meta(dt, cached=False).get_field("reference_type").options.split("\n")
	options = [option for option in options if option != "Job Card"]
	if "Work Order" not in options:
		options.append("Work Order")
	make_property_setter(dt, "reference_type", "options", "\n".join(options), "Text")
	definitions = [
		("custom_qi_basic_section", "Section Break", "基本信息"),
		("custom_qi_basic_col2", "Column Break", ""),
		("custom_qi_basic_col3", "Column Break", ""),
		("custom_qi_source_section", "Section Break", "检验来源"),
		("custom_qi_source_col2", "Column Break", ""),
		("custom_qi_source_col3", "Column Break", ""),
		("custom_qi_item_col3", "Column Break", ""),
		("custom_qi_description_section", "Section Break", "物料描述"),
		("custom_qi_quantity_section", "Section Break", "检验结论"),
		("custom_qi_quantity_col2", "Column Break", ""),
		("custom_qi_quantity_col3", "Column Break", ""),
		("custom_qi_reason_section", "Section Break", "不合格说明"),
		("custom_qi_other_section", "Section Break", "其他设置"),
	]
	create_custom_fields({dt: [dict(fieldname=name, fieldtype=kind, label=label,
		insert_after="amended_from", collapsible=int(name in ("custom_qi_description_section", "custom_qi_other_section")))
		for name, kind, label in definitions]}, update=True)
	meta = frappe.get_meta(dt, cached=False)
	order = [f.fieldname for f in meta.fields]
	block = [
		"custom_qi_basic_section", "inspection_type", "company",
		"custom_qi_basic_col2", "report_date",
		"custom_qi_basic_col3", "status",
		"custom_qi_source_section", "reference_type", "custom_purchase_order",
		"custom_qi_source_col2", "reference_name", "custom_receiving_notice",
		"custom_qi_source_col3", "custom_work_order", "custom_work_order_item",
		"section_break_7", "item_code", "item_name", "column_break1", "batch_no",
		"custom_qi_item_col3", "item_serial_no",
		"custom_qi_description_section", "description",
		"specification_details", "quality_inspection_template", "manual_inspection", "readings", "custom_purchase_quality_items",
		"custom_qi_quantity_section", "sample_size", "custom_inspection_qty",
		"custom_qi_quantity_col2", "custom_accepted_qty",
		"custom_qi_quantity_col3", "custom_rejected_qty",
		"custom_qi_reason_section", "custom_rejection_reason",
		"section_break_14", "inspected_by", "remarks", "column_break_17", "verified_by",
		"custom_qi_other_section", "naming_series", "bom_no", "amended_from",
		"child_row_reference", "custom_purchase_order_item", "custom_receiving_notice_item",
		"column_break_4", "print_settings_section", "letter_head",
	]
	# Include extension fields instead of dropping unfamiliar customizations.
	final = [name for name in block if name in order] + [name for name in order if name not in block]
	make_property_setter(dt, None, "field_order", json.dumps(final), "JSON", for_doctype=True)
	for name, label in (("section_break_7", "检验对象"), ("specification_details", "检验记录"),
		("section_break_14", "检验人员与备注")):
		make_property_setter(dt, name, "label", label, "Data")
	make_property_setter(dt, "print_settings_section", "collapsible", 1, "Check")
	frappe.clear_cache(doctype=dt)
