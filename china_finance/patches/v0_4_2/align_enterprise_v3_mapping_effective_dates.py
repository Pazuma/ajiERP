import frappe


def execute():
	"""Align pre-release 3.0 mappings before they can be frozen in a statutory snapshot."""
	for settings in frappe.get_all(
		"China Finance Settings",
		filters={"enabled": 1, "accounting_standard": "企业会计准则"},
		fields=["company", "statutory_reporting_activation_date"],
	):
		if not settings.statutory_reporting_activation_date:
			continue
		for template in frappe.get_all(
			"China Financial Statement Template",
			filters={"accounting_standard": "企业会计准则", "version": "3.0"},
			pluck="name",
		):
			if frappe.db.exists("China Report Snapshot", {"template": template}):
				continue
			for mapping_name in frappe.get_all(
				"China Financial Statement Mapping",
				filters={
					"company": settings.company, "template": template,
					"mapping_source": "Automatic", "reviewed": 0,
				},
				pluck="name",
			):
				mapping = frappe.get_doc("China Financial Statement Mapping", mapping_name)
				if mapping.effective_from == settings.statutory_reporting_activation_date:
					continue
				mapping.effective_from = settings.statutory_reporting_activation_date
				mapping.flags.ignore_permissions = True
				mapping.save()
