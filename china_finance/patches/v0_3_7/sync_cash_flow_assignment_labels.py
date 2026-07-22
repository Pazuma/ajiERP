import frappe

from china_finance.services.financial_statement import get_template


def execute():
	if not frappe.db.exists("DocType", "China Cash Flow Assignment Item"):
		return
	assignments = frappe.get_all(
		"China Cash Flow Assignment",
		fields=["name", "company", "posting_date"],
	)
	for assignment in assignments:
		template = get_template(assignment.company, "Cash Flow", assignment.posting_date)
		labels = {row.row_code: row.label for row in template.rows}
		for item in frappe.get_all(
			"China Cash Flow Assignment Item",
			filters={"parent": assignment.name},
			fields=["name", "suggested_row_code"],
		):
			label = labels.get(item.suggested_row_code)
			if label:
				frappe.db.set_value(
					"China Cash Flow Assignment Item",
					item.name,
					"suggested_row_label",
					label,
					update_modified=False,
				)
