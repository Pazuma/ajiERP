"""Keep the purchasing status chart aligned with the current reporting year."""

import json

import frappe


def ensure_buying_dashboard_chart():
	chart_name = "Material Request Analysis"
	if not frappe.db.exists("Dashboard Chart", chart_name):
		return
	filters = json.loads(frappe.db.get_value("Dashboard Chart", chart_name, "filters_json") or "[]")
	for condition in filters:
		# SQL NOT IN containing NULL excludes every status.
		if condition[:3] == ["Material Request", "status", "not in"]:
			condition[3] = [status for status in condition[3] if status is not None]
		if condition[:3] == ["Material Request", "transaction_date", "Timespan"] and condition[3] == "last quarter":
			condition[3] = "this year"
	frappe.db.set_value("Dashboard Chart", chart_name, "filters_json", json.dumps(filters), update_modified=False)
	frappe.cache.delete_key(f"chart-data:{chart_name}")
	frappe.clear_cache(doctype="Dashboard Chart")
