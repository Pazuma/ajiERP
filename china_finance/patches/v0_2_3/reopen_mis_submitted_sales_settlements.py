import frappe


def execute():
	"""Restore drafts submitted through the accidental standard DocType action in 0.2.2."""
	if not frappe.db.exists("DocType", "China Sales Settlement"):
		return
	for name in frappe.get_all(
		"China Sales Settlement",
		filters={"docstatus": 1, "status": ["in", ("草稿", "待客户确认", "待财务审批")]},
		pluck="name",
	):
		frappe.db.set_value("China Sales Settlement", name, "docstatus", 0, update_modified=False)
