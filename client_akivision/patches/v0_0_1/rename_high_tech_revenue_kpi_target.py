import frappe


def execute():
	"""Keep existing KPI Target records aligned with the dashboard wording."""
	if not frappe.db.exists("DocType", "KPI Target"):
		return

	frappe.db.set_value(
		"KPI Target",
		{"kpi_code": "high_tech_revenue"},
		"kpi_name",
		"高新收入总额",
		update_modified=False,
	)
