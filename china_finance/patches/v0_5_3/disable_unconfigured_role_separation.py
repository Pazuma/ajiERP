import frappe

from china_finance.services.voucher import GL_SOURCE_DOCTYPES
from china_finance.setup.china_coa_profile import is_profile_company


def execute():
	"""Keep a fresh China-template company usable until workflows are configured.

	Only untouched companies qualify: no GL history and no active source workflow.
	Existing operating companies and explicitly configured workflow controls remain unchanged.
	"""
	for settings in frappe.get_all(
		"China Finance Settings",
		filters={"enabled": 1, "enforce_role_separation": 1},
		fields=["name", "company"],
	):
		if not is_profile_company(settings.company):
			continue
		if frappe.db.exists("GL Entry", {"company": settings.company}):
			continue
		if frappe.db.exists(
			"Workflow",
			{"document_type": ["in", list(GL_SOURCE_DOCTYPES)], "is_active": 1},
		):
			continue
		frappe.db.set_value(
			"China Finance Settings", settings.name, "enforce_role_separation", 0, update_modified=False
		)
