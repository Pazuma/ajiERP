"""Explicit, transactional replacement of collection-mode master data."""

import frappe

MODES = (
	("1", "预付款", 0), ("2", "货到付款", 0), ("3", "月结30天", 30),
	("4", "月结60天", 60), ("5", "票后7天", 7), ("6", "票后30天", 30), ("7", "票后60天", 60),
)


def audit():
	names = frappe.get_all("Payment Terms Template", pluck="name")
	links = []
	fields = frappe.get_all("DocField", filters={"fieldtype": "Link", "options": "Payment Terms Template"}, fields=["parent", "fieldname"])
	fields += [frappe._dict(parent=f.dt, fieldname=f.fieldname) for f in frappe.get_all(
		"Custom Field", filters={"fieldtype": "Link", "options": "Payment Terms Template"}, fields=["dt", "fieldname"])]
	for field in fields:
		if not frappe.db.table_exists(field.parent) or not frappe.db.has_column(field.parent, field.fieldname):
			continue
		for row in frappe.get_all(field.parent, filters={field.fieldname: ["in", names]}, fields=["name", field.fieldname]):
			links.append({"doctype": field.parent, "name": row.name, "field": field.fieldname, "mode": row.get(field.fieldname)})
	return {"old_modes": names, "references": links}


def replace():
	"""Run manually only; never delete user-maintained modes during migrations."""
	frappe.only_for("System Manager")
	before = audit()
	if before["references"]:
		frappe.throw("现有收款模式仍被单据引用，暂未删除，请先检查 receipt_modes.audit 输出。")
	frappe.db.savepoint("replace_receipt_modes")
	try:
		for name in before["old_modes"]:
			frappe.delete_doc("Payment Terms Template", name)
		for code, title, days in MODES:
			term_name = f"收款模式-{code}-{title}"
			term = frappe.get_doc("Payment Term", term_name) if frappe.db.exists("Payment Term", term_name) else frappe.new_doc("Payment Term")
			term.update({"payment_term_name": term_name, "invoice_portion": 100,
				"due_date_based_on": "Day(s) after the end of the invoice month" if title.startswith("月结") else "Day(s) after invoice date",
				"credit_days": days, "credit_months": 0})
			term.save()
			frappe.get_doc({"doctype": "Payment Terms Template", "template_name": title, "custom_mode_code": code,
				"terms": [{"payment_term": term.name, "invoice_portion": 100,
					"due_date_based_on": term.due_date_based_on, "credit_days": days, "credit_months": 0}]}).insert()
		frappe.clear_cache(doctype="Payment Terms Template")
	except Exception:
		frappe.db.rollback(save_point="replace_receipt_modes")
		raise
	return {"removed": before["old_modes"], "created": MODES}
