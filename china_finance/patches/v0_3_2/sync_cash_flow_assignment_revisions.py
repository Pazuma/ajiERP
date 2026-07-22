import frappe


def execute():
	if not frappe.db.exists("DocType", "China Cash Flow Assignment"):
		return

	assignments = frappe.get_all(
		"China Cash Flow Assignment",
		fields=["name", "china_accounting_voucher", "revision", "assignment_key"],
		order_by="china_accounting_voucher asc, creation asc",
	)
	revisions = {}
	for assignment in assignments:
		voucher = assignment.china_accounting_voucher
		revisions[voucher] = revisions.get(voucher, 0) + 1
		revision = revisions[voucher]
		key = f"{voucher}|{revision}"
		if assignment.revision != revision or assignment.assignment_key != key:
			frappe.db.set_value(
				"China Cash Flow Assignment",
				assignment.name,
				{"revision": revision, "assignment_key": key},
				update_modified=False,
			)

	frappe.db.add_unique("China Cash Flow Assignment", "assignment_key", "unique_cash_flow_assignment_key")
