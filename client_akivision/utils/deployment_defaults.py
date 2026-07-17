import frappe


SAMPLE_LOAN_WAREHOUSES = ("Customer Loan", "Supplier Loan")


def sync_deployment_defaults():
	"""Restore required configuration records without replacing user settings."""
	from client_akivision.patches.v0_0_1 import (
		allow_remarks_after_submit,
		create_engineering_drawing_workflow,
		enable_engineering_drawing_workflow_status_colours,
		seed_aging_period_rules,
		seed_purchase_delay_risk_rules,
		set_finalized_workflow_state_success,
		sync_sample_loan_out_aki_naming_series,
	)

	seed_aging_period_rules.execute()
	seed_purchase_delay_risk_rules.execute()
	create_engineering_drawing_workflow.execute()
	enable_engineering_drawing_workflow_status_colours.execute()
	set_finalized_workflow_state_success.execute()
	allow_remarks_after_submit.execute()
	sync_sample_loan_out_aki_naming_series.execute()
	ensure_sample_loan_warehouses()
	validate_deployment_defaults()


def ensure_sample_loan_warehouses():
	for company in frappe.get_all("Company", filters={"is_group": 0}, pluck="name"):
		for warehouse_name in SAMPLE_LOAN_WAREHOUSES:
			if frappe.db.exists("Warehouse", {"warehouse_name": warehouse_name, "company": company}):
				continue

			frappe.get_doc(
				{
					"doctype": "Warehouse",
					"warehouse_name": warehouse_name,
					"company": company,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)


def validate_deployment_defaults():
	missing = []
	if not frappe.db.count("Aging Period Rule"):
		missing.append("Aging Period Rule defaults")
	if not frappe.db.count("Purchase Delay Risk Rule"):
		missing.append("Purchase Delay Risk Rule defaults")
	if not frappe.db.exists("Workflow", {"document_type": "Engineering Drawing", "is_active": 1}):
		missing.append("Engineering Drawing workflow")

	for doctype in ("Stock Entry", "Purchase Receipt"):
		if not frappe.db.exists(
			"Property Setter",
			{
				"doc_type": doctype,
				"field_name": "remarks",
				"property": "allow_on_submit",
				"value": "1",
			},
		):
			missing.append(f"{doctype}.remarks allow_on_submit")

	for company in frappe.get_all("Company", filters={"is_group": 0}, pluck="name"):
		for warehouse_name in SAMPLE_LOAN_WAREHOUSES:
			if not frappe.db.exists("Warehouse", {"warehouse_name": warehouse_name, "company": company}):
				missing.append(f"{company}: {warehouse_name} warehouse")

	if missing:
		frappe.throw("Missing client_akivision deployment defaults:\n" + "\n".join(missing))
