"""Refresh statutory rows for the small-enterprise v3 templates."""

import frappe


def execute():
	if not frappe.db.exists("DocType", "China Financial Statement Template"):
		return
	from china_finance.setup.templates import (
		ensure_company_mappings,
		refresh_small_enterprise_v3_templates,
	)
	refresh_small_enterprise_v3_templates()
	ensure_company_mappings()
