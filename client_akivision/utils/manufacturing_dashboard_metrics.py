"""Keep standard manufacturing workspace number cards localized and current."""

import json

import frappe


CARDS = {
	"Monthly Total Work Order": {
		"label": "本月工单数",
		"filters": [["Work Order", "docstatus", "=", 1], ["Work Order", "creation", "Timespan", "this month"]],
	},
	"Monthly Completed Work Order": {
		"label": "本月已完成工单数",
		"filters": [["Work Order", "status", "=", "Completed"], ["Work Order", "docstatus", "=", 1], ["Work Order", "creation", "Timespan", "this month"]],
	},
	"Ongoing Job Card": {
		"label": "进行中工序数",
		"filters": [["Job Card", "status", "not in", ["Completed", "Cancelled"]], ["Job Card", "docstatus", "=", 1]],
	},
	"Monthly Quality Inspection": {
		"label": "本月质检单数",
		"filters": [["Quality Inspection", "docstatus", "=", 1], ["Quality Inspection", "creation", "Timespan", "this month"]],
	},
}


def ensure_manufacturing_dashboard_cards():
	"""Update existing ERPNext KPI cards without changing their workspace placement."""
	for name, config in CARDS.items():
		if not frappe.db.exists("Number Card", name):
			continue
		frappe.db.set_value("Number Card", name, {
			"label": config["label"],
			"filters_json": json.dumps(config["filters"], ensure_ascii=False),
		}, update_modified=False)
		frappe.cache.delete_key(f"number_card:{name}")
	frappe.clear_cache(doctype="Number Card")
	frappe.clear_cache(doctype="Workspace")
