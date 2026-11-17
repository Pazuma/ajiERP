"""Keep manufacturing dashboard charts arranged side by side."""

import frappe


CHARTS = {"Work Order Qty Analysis", "Job Card Analysis"}


def ensure_manufacturing_dashboard_chart_widths():
	"""Set the two manufacturing analysis charts to half-width."""
	if not frappe.db.exists("Dashboard", "Manufacturing"):
		return

	dashboard = frappe.get_doc("Dashboard", "Manufacturing")
	changed = False
	for row in dashboard.charts:
		if row.chart in CHARTS and row.width != "Half":
			row.width = "Half"
			changed = True

	if changed:
		dashboard.save(ignore_permissions=True)
		frappe.clear_cache(doctype="Dashboard")
