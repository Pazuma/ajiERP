import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import now_datetime


def execute():
	fields = {"System Settings": [{"fieldname": "auto_draft_finance_enabled_at",
		"label": "Finance Auto Draft Reminder Enabled At", "fieldtype": "Datetime",
		"hidden": 1, "read_only": 1}]}
	if frappe.db.exists("DocType", "Purchase Follow Up"):
		fields["Purchase Follow Up"] = [{"fieldname": "auto_reconciliation_statement",
			"label": "自动创建来源对账单", "fieldtype": "Link",
			"options": "China Reconciliation Statement", "hidden": 1, "read_only": 1}]
	create_custom_fields(fields)
	if not frappe.db.get_single_value("System Settings", "auto_draft_finance_enabled_at"):
		frappe.db.set_single_value("System Settings", "auto_draft_finance_enabled_at", now_datetime())
