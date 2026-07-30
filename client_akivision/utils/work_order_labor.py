"""Simple work-order-level labor costing without Job Cards."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def ensure_schema():
	create_custom_fields(
		{
			"Company": [{"fieldname": "custom_labor_hourly_rate", "label": "默认人工小时费率", "fieldtype": "Currency", "description": "新建生产工单时自动带入，可在生产工单上按实际情况调整。", "insert_after": "default_currency"}],
			"Employee": [{"fieldname": "custom_labor_hourly_rate", "label": "人工小时费率", "fieldtype": "Currency", "description": "用于生产工单人工成本计算。", "insert_after": "company"}],
			"Work Order": [
				{"fieldname": "custom_labor_cost_section", "label": "人工成本", "fieldtype": "Section Break", "insert_after": "actual_end_date"},
				{"fieldname": "custom_actual_labor_hours", "label": "实际人工工时", "fieldtype": "Float", "description": "填写整张生产工单实际投入的人工小时数。", "allow_on_submit": 1, "insert_after": "custom_labor_cost_section"},
				{"fieldname": "custom_labor_hourly_rate", "label": "人工小时费率", "fieldtype": "Currency", "description": "默认取自公司设置，也可以在本工单调整。", "allow_on_submit": 1, "insert_after": "custom_actual_labor_hours"},
				{"fieldname": "custom_actual_labor_cost", "label": "实际人工成本", "fieldtype": "Currency", "read_only": 1, "allow_on_submit": 1, "description": "实际人工工时 × 人工小时费率。", "insert_after": "custom_labor_hourly_rate"},
				{"fieldname": "custom_labor_details", "label": "人工明细", "fieldtype": "Table", "options": "Work Order Labor Item", "allow_on_submit": 1, "insert_after": "custom_actual_labor_cost"},
			],
		},
		update=True,
	)
	for doctype in ("Company", "Work Order"):
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)


def calculate_labor_cost(doc, method=None):
	if not doc.get("company") or not doc.get("production_item"):
		return
	if not doc.get("custom_labor_hourly_rate"):
		doc.custom_labor_hourly_rate = frappe.db.get_value("Company", doc.company, "custom_labor_hourly_rate") or 0
	if doc.get("custom_labor_details"):
		labor_cost = 0
		hours = 0
		for row in doc.custom_labor_details:
			row.hourly_rate = flt(row.hourly_rate) or flt(frappe.db.get_value("Employee", row.employee, "custom_labor_hourly_rate")) or flt(doc.get("custom_labor_hourly_rate"))
			row.labor_cost = flt(row.hours) * flt(row.hourly_rate)
			hours += flt(row.hours)
			labor_cost += flt(row.labor_cost)
		doc.custom_actual_labor_hours = hours
		doc.custom_labor_hourly_rate = labor_cost / hours if hours else 0
	else:
		hours = flt(doc.get("custom_actual_labor_hours"))
		labor_cost = hours * flt(doc.get("custom_labor_hourly_rate"))
	old_cost = flt((doc.get_doc_before_save() or {}).get("custom_actual_labor_cost"))
	doc.custom_actual_labor_cost = labor_cost
	doc.actual_operating_cost = flt(doc.get("actual_operating_cost")) - old_cost + labor_cost
	if doc.get("total_operating_cost"):
		doc.total_operating_cost = flt(doc.total_operating_cost) - old_cost + labor_cost
