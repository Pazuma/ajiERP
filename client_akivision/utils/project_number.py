"""Generate the business-facing Project serial number."""

from frappe.model.naming import make_autoname
from frappe.utils import nowdate


def assign_project_number(doc, method=None):
	"""Assign a PRO serial only to new projects that do not already have one."""
	if not doc.get("custom_project_code"):
		doc.custom_project_code = make_autoname(f"PRO-{nowdate().replace('-', '')}-.#####")
