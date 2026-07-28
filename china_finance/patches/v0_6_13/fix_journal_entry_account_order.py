"""Keep the Journal Entry Account grid useful for Chinese finance users."""

import json

import frappe


FIELD_ORDER = [
	"user_remark",
	"account",
	"account_type",
	"party_type",
	"party",
	"debit_in_account_currency",
	"debit",
	"credit_in_account_currency",
	"credit",
	"cost_center",
	"project",
	"accounting_dimensions_section",
	"dimension_col_break",
	"currency_section",
	"account_currency",
	"column_break_10",
	"exchange_rate",
	"sec_break1",
	"reference",
	"reference_type",
	"reference_name",
	"reference_due_date",
	"reference_detail_no",
	"advance_voucher_type",
	"advance_voucher_no",
	"is_tax_withholding_account",
	"col_break1",
	"col_break2",
	"col_break3",
	"is_advance",
	"against_account",
]


def _upsert_property(field_name, property_name, value, property_type):
	filters = {
		"doctype_or_field": "DocType" if field_name is None else "DocField",
		"doc_type": "Journal Entry Account",
		"field_name": field_name,
		"property": property_name,
	}
	name = frappe.db.exists("Property Setter", filters)
	if name:
		if frappe.db.get_value("Property Setter", name, "value") != value:
			frappe.db.set_value("Property Setter", name, "value", value, update_modified=False)
		return

	frappe.get_doc(
		{
			"doctype": "Property Setter",
			**filters,
			"value": value,
			"property_type": property_type,
			"is_system_generated": 1,
		}
	).insert(ignore_permissions=True)


def execute():
	_upsert_property(None, "field_order", json.dumps(FIELD_ORDER), "JSON")
	_upsert_property("user_remark", "label", "摘要", "Data")
	_upsert_property("user_remark", "in_list_view", "1", "Check")
	frappe.clear_cache(doctype="Journal Entry Account")
