"""Apply Chinese labels to the standard Unit of Measure list and form."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


LABELS = {
	"uom_name": "单位名称",
	"category": "类别",
	"symbol": "符号",
	"common_code": "通用代码",
	"description": "说明",
	"enabled": "启用",
	"must_be_whole_number": "必须为整数",
}


def ensure_chinese_labels():
	for fieldname, label in LABELS.items():
		if not frappe.get_meta("UOM").has_field(fieldname):
			continue
		make_property_setter("UOM", fieldname, "label", label, "Data")
	make_property_setter("UOM", None, "title_field", "uom_name", "Data", for_doctype=True)
	make_property_setter("UOM", "uom_name", "in_list_view", 0, "Check")
	make_property_setter("UOM", "enabled", "in_list_view", 1, "Check")
	make_property_setter("UOM", "category", "in_list_view", 1, "Check")
	frappe.clear_cache(doctype="UOM")


def ensure_item_code_naming():
	"""Ensure manually entered Product code remains the canonical Item name."""
	frappe.db.set_default("item_naming_by", "Item Code")
	frappe.clear_cache(doctype="Item")
