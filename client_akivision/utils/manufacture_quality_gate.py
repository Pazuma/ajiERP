"""Quality gate for finished-goods manufacture stock entries."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def ensure_schema():
	create_custom_fields(
		{
			"Quality Inspection": [
				{"fieldname": "custom_work_order", "label": "来源生产工单", "fieldtype": "Link", "options": "Work Order", "insert_after": "reference_name"},
				{"fieldname": "custom_work_order_item", "label": "来源工单成品", "fieldtype": "Data", "read_only": 1, "insert_after": "custom_work_order"},
				{"fieldname": "custom_inspection_qty", "label": "报检数量", "fieldtype": "Float", "insert_after": "custom_work_order_item"},
				{"fieldname": "custom_accepted_qty", "label": "合格数量", "fieldtype": "Float", "insert_after": "custom_inspection_qty"},
				{"fieldname": "custom_rejected_qty", "label": "不合格数量", "fieldtype": "Float", "insert_after": "custom_accepted_qty"},
				{"fieldname": "custom_rejection_reason", "label": "不合格原因", "fieldtype": "Small Text", "insert_after": "custom_rejected_qty"},
			],
			"Stock Entry": [
				{"fieldname": "custom_quality_inspection", "label": "完工质检单", "fieldtype": "Link", "options": "Quality Inspection", "read_only": 1, "insert_after": "work_order"},
			],
		},
		update=True,
	)
	for doctype in ("Quality Inspection", "Stock Entry"):
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def validate_quality_inspection(doc, method=None):
	if not doc.get("custom_work_order"):
		return
	qty = flt(doc.get("custom_inspection_qty"))
	accepted = flt(doc.get("custom_accepted_qty"))
	rejected = flt(doc.get("custom_rejected_qty"))
	if qty <= 0:
		frappe.throw(_("生产质检的报检数量必须大于 0。"))
	if accepted < 0 or rejected < 0 or accepted + rejected > qty:
		frappe.throw(_("生产质检的合格数和不合格数无效。"))
	if rejected and not doc.get("custom_rejection_reason"):
		frappe.throw(_("生产质检存在不合格数量时必须填写不合格原因。"))
	if accepted + rejected < qty:
		doc.status = "Pending"
	elif rejected:
		doc.status = "Rejected" if not accepted else "Accepted"
	else:
		doc.status = "Accepted"


def validate_manufacture_entry(doc, method=None):
	if doc.get("purpose") != "Manufacture" or not doc.get("work_order"):
		return
	finished_qty = flt(doc.get("fg_completed_qty"))
	if finished_qty <= 0:
		return
	inspection = frappe.db.get_value(
		"Quality Inspection",
		{"custom_work_order": doc.work_order, "docstatus": 1, "status": "Accepted"},
		["name", "custom_accepted_qty"],
		as_dict=True,
	)
	if not inspection or flt(inspection.custom_accepted_qty) < finished_qty:
		frappe.throw(_("生产入库必须先完成合格质检，且合格数量不得少于本次入库数量。"))
	doc.custom_quality_inspection = inspection.name

