import json

import frappe


def execute():
	"""Keep the native trial balance available at its own route, not in this picker."""
	if not frappe.db.exists("Report", "China Financial Statements"):
		return

	report = frappe.get_doc("Report", "China Financial Statements")
	filters = report.filters or []
	if isinstance(filters, str):
		filters = json.loads(filters or "[]")
	changed = False
	for row in filters:
		fieldname = row.get("fieldname") if isinstance(row, dict) else row.fieldname
		current_options = row.get("options") if isinstance(row, dict) else row.options
		if fieldname == "statement_type":
			options = [option for option in (current_options or "").splitlines() if option != "Trial Balance"]
			new_options = "\n".join(options)
			if current_options != new_options:
				if isinstance(row, dict):
					row["options"] = new_options
				else:
					row.options = new_options
				changed = True
		elif fieldname == "expand_party":
			current_default = row.get("default") if isinstance(row, dict) else row.default
			if current_default != 1:
				if isinstance(row, dict):
					row["default"] = 1
				else:
					row.default = 1
			changed = True

	if changed:
		report.filters = filters
		report.save(ignore_permissions=True, ignore_version=True)
		frappe.clear_cache()
