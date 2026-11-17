"""Project-level manual cost detail schema and validation."""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


ALLOWED_COST_TYPES = {"物料消耗", "测试费", "其他费用"}


def ensure_schema():
	"""Create the Project cost detail fields idempotently."""
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "custom_project_cost_details_section",
					"label": "成本明细",
					"fieldtype": "Section Break",
					"insert_after": "cost_center",
				},
				{
					"fieldname": "custom_project_cost_details",
					"label": "成本明细",
					"fieldtype": "Table",
					"options": "Project Cost Detail",
					"insert_after": "custom_project_cost_details_section",
				},
				{
					"fieldname": "custom_project_cost_detail_total",
					"label": "成本明细合计",
					"fieldtype": "Currency",
					"options": "Company:company:default_currency",
					"read_only": 1,
					"insert_after": "custom_project_cost_details",
				},
			]
		},
		update=True,
	)
	frappe.db.updatedb("Project")
	frappe.clear_cache(doctype="Project")


def calculate_project_cost_detail_total(doc):
	"""Validate rows and calculate the authoritative detail total."""
	total = 0
	for row in doc.get("custom_project_cost_details") or []:
		if row.get("cost_type") not in ALLOWED_COST_TYPES:
			frappe.throw(_("成本明细第 {0} 行必须选择有效的成本类型。").format(row.idx))
		if row.get("cost_type") == "物料消耗" and not row.get("item_code"):
			frappe.throw(_("成本明细第 {0} 行为物料消耗时必须填写物料编码。").format(row.idx))
		if row.get("cost_type") != "物料消耗" and row.get("item_code"):
			frappe.throw(_("成本明细第 {0} 行为非物料费用时不能填写物料编码。").format(row.idx))
		if not row.get("expense_description"):
			frappe.throw(_("成本明细第 {0} 行必须填写费用说明。").format(row.idx))
		if not row.get("cost_date"):
			frappe.throw(_("成本明细第 {0} 行必须填写日期。").format(row.idx))
		if row.get("amount") in (None, ""):
			frappe.throw(_("成本明细第 {0} 行必须填写金额。").format(row.idx))
		if flt(row.get("amount")) < 0:
			frappe.throw(_("成本明细第 {0} 行金额不能为负数。").format(row.idx))
		total += flt(row.get("amount"))

	doc.custom_project_cost_detail_total = total
	return total


def validate_project_cost_details(doc, method=None):
	"""Calculate detail total and expose it in the project's total cost."""
	detail_total = calculate_project_cost_detail_total(doc)
	# The standard Project total is recalculated from submitted Timesheets by
	# ERPNext. Add the manual cost details without incrementing the existing
	# value, so repeated saves remain idempotent.
	timesheet_total = frappe.db.sql(
		"""select coalesce(sum(base_costing_amount), 0)
		from `tabTimesheet Detail`
		where project = %s and docstatus = 1""",
		doc.name,
	)[0][0]
	doc.total_costing_amount = flt(timesheet_total) + detail_total


def recalculate_project_cost(project):
	"""Recalculate and persist cost totals for an existing Project."""
	doc = frappe.get_doc("Project", project)
	validate_project_cost_details(doc)
	doc.db_set(
		{
			"custom_project_cost_detail_total": doc.custom_project_cost_detail_total,
			"total_costing_amount": doc.total_costing_amount,
		},
		update_modified=False,
	)
	return {
		"custom_project_cost_detail_total": doc.custom_project_cost_detail_total,
		"total_costing_amount": doc.total_costing_amount,
	}
