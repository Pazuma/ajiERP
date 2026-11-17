"""Small custom extensions for the standard Selling dashboard cards."""

import frappe


def ensure_selling_dashboard_cards():
	"""Create compatible number cards and attach them to the standard Selling dashboard."""
	if not frappe.db.exists("Dashboard", "Selling"):
		return
	cards = [
		{
			"name": "总订单数",
			"label": "总订单数",
			"function": "Count",
			"aggregate_function_based_on": "",
			"filters_json": '[["Sales Order","docstatus","=","1"]]',
		},
		{
			"name": "总销售额",
			"label": "总销售额",
			"aggregate_function_based_on": "base_grand_total",
			"filters_json": '[["Sales Order","docstatus","=","1"]]',
		},
		{
			"name": "整单已完成",
			"label": "整单已完成",
			"function": "Count",
			"aggregate_function_based_on": "",
			"filters_json": '[["Sales Order","docstatus","=","1"],["Sales Order","per_delivered",">=",100],["Sales Order","per_billed",">=",100]]',
		},
	]
	for card in cards:
		payload = {"doctype": "Number Card", "name": card["name"], "label": card["label"], "type": "Document Type", "document_type": "Sales Order", "function": card.get("function", "Sum"), "is_public": 1, "is_standard": 1, **{key: value for key, value in card.items() if key not in {"name", "label", "function"}}}
		if not frappe.db.exists("Number Card", card["name"]):
			frappe.get_doc(payload).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Number Card", card["name"], {key: value for key, value in payload.items() if key not in {"doctype", "name"}}, update_modified=False)
	# Link validation for Dashboard child rows reads committed Number Card rows.
	frappe.db.commit()

	dashboard = frappe.get_doc("Dashboard", "Selling")
	card_names = {row.card for row in dashboard.cards}
	for card in cards:
		if card["name"] not in card_names:
			dashboard.append("cards", {"card": card["name"]})
	# Reuse ERPNext's standard status-analysis donut; only attach it to the
	# dashboard when it is not already present.
	chart_name = "Sales Order Analysis"
	if frappe.db.exists("Dashboard Chart", chart_name) and not any(row.chart == chart_name for row in dashboard.charts):
		dashboard.append("charts", {"chart": chart_name})
	if dashboard.has_value_changed("cards") or dashboard.has_value_changed("charts"):
		# Standard dashboards are protected outside developer mode. This hook runs
		# during migrations, where these controlled child-row additions are safe.
		dashboard.flags.ignore_validate = True
		developer_mode = frappe.conf.developer_mode
		try:
			# Avoid exporting this runtime customization into ERPNext's source tree.
			frappe.conf.developer_mode = 0
			dashboard.save(ignore_permissions=True)
		finally:
			frappe.conf.developer_mode = developer_mode
	# The current UI renders the Selling workspace (not the legacy Dashboard).
	if frappe.db.exists("Workspace", "Selling"):
		workspace = frappe.get_doc("Workspace", "Selling")
		workspace_card_names = {row.number_card_name for row in workspace.number_cards}
		for card in cards:
			if card["name"] not in workspace_card_names:
				workspace.append("number_cards", {"number_card_name": card["name"], "label": card["label"]})
		if workspace.has_value_changed("number_cards"):
			workspace.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Dashboard")
	frappe.clear_cache(doctype="Workspace")
