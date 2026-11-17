"""Contact import conveniences for mixed business spreadsheets."""


def ensure_primary_contact_numbers(doc, method=None):
	"""Make the first imported phone/email the primary value when none is marked."""
	for table_field, primary_field in (("phone_nos", "is_primary_mobile_no"), ("email_ids", "is_primary")):
		rows = doc.get(table_field) or []
		if rows and not any(row.get(primary_field) for row in rows):
			rows[0].set(primary_field, 1)
