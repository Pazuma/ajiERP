import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	ensure_supplier_rating_field()
	ensure_scorecard_variable()
	ensure_scorecard_criteria()
	ensure_scorecard_standings()


def ensure_supplier_rating_field():
	create_custom_fields(
		{
			"Supplier": [
				{
					"fieldname": "custom_supplier_rating",
					"label": "Supplier Rating",
					"fieldtype": "Data",
					"insert_after": "prevent_pos",
					"read_only": 1,
					"translatable": 0,
				}
			]
		},
		update=True,
	)
	frappe.db.updatedb("Supplier")
	frappe.clear_cache(doctype="Supplier")


def ensure_scorecard_variable():
	upsert(
		"Supplier Scorecard Variable",
		"Average Delay Days",
		{
			"variable_label": "Average Delay Days",
			"param_name": "avg_days_late",
			"path": "client_akivision.utils.supplier_scorecard.get_avg_days_late",
			"is_custom": 1,
			"description": "Average delay days per shipment for the period",
		},
	)


def ensure_scorecard_criteria():
	criteria = (
		{
			"criteria_name": "到货及时率",
			"max_score": 100,
			"weight": 60,
			"formula": "({on_time_shipment_num} / {total_shipments}) * 100",
		},
		{
			"criteria_name": "平均延迟天数",
			"max_score": 100,
			"weight": 40,
			"formula": "max(0, 100 - ({avg_days_late} * 10))",
		},
	)
	for values in criteria:
		upsert("Supplier Scorecard Criteria", values["criteria_name"], values)


def ensure_scorecard_standings():
	standings = (
		{"standing_name": "A级", "standing_color": "Blue", "min_grade": 90, "max_grade": 100},
		{"standing_name": "B级", "standing_color": "Green", "min_grade": 80, "max_grade": 90},
		{"standing_name": "C级", "standing_color": "Yellow", "min_grade": 60, "max_grade": 80},
		{
			"standing_name": "D级",
			"standing_color": "Red",
			"min_grade": 0,
			"max_grade": 60,
			"warn_pos": 1,
		},
	)
	for values in standings:
		upsert("Supplier Scorecard Standing", values["standing_name"], values)


def upsert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		doc.update(values)
		doc.save(ignore_permissions=True)
		return

	frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)
