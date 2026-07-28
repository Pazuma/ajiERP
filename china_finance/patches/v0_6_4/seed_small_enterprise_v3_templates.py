"""Seed the complete small-enterprise statement templates and suggestions."""

import frappe


def execute():
	from china_finance.setup.templates import (
		ensure_company_mappings,
		refresh_small_enterprise_v3_templates,
		seed_statement_templates,
	)

	if not frappe.db.exists("DocType", "China Financial Statement Template"):
		return
	seed_statement_templates()
	refresh_small_enterprise_v3_templates()
	ensure_company_mappings()
