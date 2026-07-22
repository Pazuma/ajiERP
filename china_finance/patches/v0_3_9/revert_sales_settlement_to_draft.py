import frappe


def execute():
	"""Revert submitted-but-not-invoiced settlements to draft for the single-submit flow."""
	if not frappe.db.exists("DocType", "China Sales Settlement"):
		return

	legacy_statuses = ["待客户确认", "待财务审批"]
	frappe.db.set_value(
		"China Sales Settlement",
		{"status": ["in", legacy_statuses], "docstatus": 1},
		"docstatus",
		0,
		update_modified=False,
	)
	frappe.db.set_value(
		"China Sales Settlement",
		{"status": ["in", legacy_statuses]},
		"status",
		"草稿",
		update_modified=False,
	)
