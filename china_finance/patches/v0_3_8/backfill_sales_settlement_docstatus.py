import frappe


def execute():
	"""Backfill docstatus after China Sales Settlement became submittable."""
	if not frappe.db.exists("DocType", "China Sales Settlement"):
		return

	frappe.db.set_value(
		"China Sales Settlement",
		{"status": ["in", ["待客户确认", "待财务审批", "已生成应收"]], "docstatus": 0},
		"docstatus",
		1,
		update_modified=False,
	)
	frappe.db.set_value(
		"China Sales Settlement",
		{"status": "已取消", "docstatus": 0},
		"docstatus",
		2,
		update_modified=False,
	)
