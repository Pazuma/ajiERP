import frappe


def execute():
	"""Enable imports for manual sample forms and keep generated status read-only."""
	for doctype in ("Finished Goods Status", "Sample Loan Out", "Sample Loan In"):
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_doc("DocType", doctype)
		should_allow = doctype in ("Sample Loan Out", "Sample Loan In")
		if bool(meta.allow_import) != should_allow:
			meta.allow_import = 1 if should_allow else 0
			meta.save(ignore_permissions=True)
		frappe.clear_cache(doctype=doctype)
