import frappe


SOURCE_TEXT = "Source of Funds (Liabilities)"
TRANSLATED_TEXT = "负债"


def execute():
	"""Use the standard Chinese accounting name for the liability root."""
	name = frappe.db.exists(
		"Translation", {"source_text": SOURCE_TEXT, "language": "zh"}
	)

	if name:
		frappe.db.set_value(
			"Translation",
			name,
			"translated_text",
			TRANSLATED_TEXT,
			update_modified=False,
		)
		return

	frappe.get_doc(
		{
			"doctype": "Translation",
			"language": "zh",
			"source_text": SOURCE_TEXT,
			"translated_text": TRANSLATED_TEXT,
		}
	).insert(ignore_permissions=True)
