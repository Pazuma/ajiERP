from client_akivision.utils.misc_purchase import ensure_schema


def execute():
	"""Install the idempotent schema and generic item used by miscellaneous purchases."""
	ensure_schema()
