"""Recover raw bank summaries for transactions imported before the custom field."""

import frappe


def execute():
	# The custom field is created by after_migrate and may not exist yet when
	# post-model patches run during the first migration.
	if not frappe.db.has_column("Bank Transaction", "custom_summary"):
		return
	rows = frappe.get_all(
		"Bank Transaction",
		filters={"custom_summary": ["in", ["", None]]},
		fields=["name", "description"],
	)
	for row in rows:
		description = (row.description or "").strip()
		if "｜" not in description:
			continue
		summary = description.split("｜", 1)[0].strip()
		if summary:
			frappe.db.set_value("Bank Transaction", row.name, "custom_summary", summary, update_modified=False)
