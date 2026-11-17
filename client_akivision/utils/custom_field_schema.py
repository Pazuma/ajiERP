import frappe
from frappe.model import NO_VALUE_FIELDS


REQUIRED_FIELDS = {
	"Item": (
		"custom_internal_model",
		"custom_external_model",
		"custom_product_type",
		"custom_product_category",
		"custom_product_name",
		"custom_applicable_model",
		"custom_version",
		"custom_product_status",
		"custom_remarks",
		"custom_safety_stock_remarks",
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
		"custom_live_stock_version",
		"custom_live_stock_applicable_model",
		"custom_live_stock_category",
		"custom_live_stock_opening_qty",
		"custom_live_stock_total_in_qty",
		"custom_live_stock_total_out_qty",
		"custom_live_stock_qty",
		"custom_live_stock_new_warehouse",
		"custom_live_stock_count_date",
		"custom_live_stock_unit_price",
		"custom_live_stock_total_value",
		"custom_live_stock_remarks",
		"custom_live_stock_old_warehouse",
	),
	"Item Reorder": ("custom_max_stock_limit",),
	"Serial No": (
		"custom_akivision_status",
		"custom_akivision_loan_out",
		"custom_akivision_customer",
		"custom_akivision_sales_order",
		"custom_akivision_loan_in",
		"custom_akivision_supplier",
	),
	"Stock Entry": (
		"custom_stock_direction",
		"custom_stock_reason",
		"custom_akivision_sample_loan_doctype",
		"custom_akivision_sample_loan_doc",
		"custom_excel_receipt_type",
		"custom_excel_delivery_note",
		"custom_excel_supplier_name",
		"custom_excel_lens_receipt_no",
		"custom_excel_reconciliation_date",
		"custom_excel_operator",
		"custom_excel_source_row",
		"custom_excel_outbound_no",
		"custom_excel_issue_category",
		"custom_excel_model",
		"custom_excel_explanation",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Stock Entry Detail": (
		"custom_manual_batch_no",
		"custom_excel_item_name",
		"custom_excel_version",
		"custom_excel_applicable_model",
		"custom_excel_item_group",
		"custom_excel_total_amount",
		"custom_excel_source_qty",
		"custom_excel_delivery_note",
		"custom_excel_purchase_order",
		"custom_excel_warehouse",
		"custom_excel_source_row",
		"custom_excel_expected_qty",
		"custom_excel_model",
		"custom_excel_issue_category",
		"custom_excel_explanation",
	),
	"Supplier": ("custom_supplier_rating", "custom_rating_standard", "custom_quote_column_mapping", "custom_quote_item_mapping", "custom_review_total_orders", "custom_review_on_time_orders", "custom_review_on_time_rate", "custom_review_delayed_orders", "custom_review_average_delay_days", "custom_review_rating"),
	"Sales Order": ("custom_is_high_tech_revenue", "custom_remarks", "custom_sales_person", "custom_progress_milestone_code", "custom_progress_step_name", "custom_progress_actual_completed_on"),
	"Delivery Note": (
		"custom_remarks",
		"custom_excel_year",
		"custom_excel_month",
		"custom_excel_customer_code",
        "custom_excel_customer_name",
        "custom_excel_sales_person",
        "custom_sales_order",
		"custom_excel_delivery_no",
		"custom_excel_invoice_no",
		"custom_excel_invoice_date",
		"custom_excel_order_status",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Payment Entry": (
		"custom_excel_payment_history_section",
		"custom_excel_year",
		"custom_excel_model",
		"custom_excel_month",
		"custom_excel_order_no",
		"custom_excel_invoice_date",
		"custom_excel_sales_person",
		"custom_excel_total_amount",
		"custom_excel_customer_code",
		"custom_excel_customer_name",
		"custom_excel_delivery_date",
		"custom_excel_delivery_note",
		"custom_excel_internal_model",
		"custom_excel_invoice_issued",
		"custom_excel_payment_status",
		"custom_excel_receivable_days",
		"custom_excel_unreceived_amount",
		"custom_excel_payment_term_range",
		"custom_excel_agreed_payment_date",
	),
	"BOM": ("custom_excel_model", "custom_excel_item_name", "custom_excel_drawing_no"),
	"BOM Item": ("custom_excel_model", "custom_excel_item_name", "custom_excel_drawing_no", "custom_excel_level"),
	"Purchase Receipt": (
		"custom_purchase_order",
		"custom_lens_receipt_no",
		"custom_reconciliation_date",
		"custom_excel_receipt_type",
		"custom_excel_delivery_note",
		"custom_excel_supplier_name",
		"custom_excel_operator",
		"custom_excel_source_row",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Purchase Receipt Item": (
		"custom_excel_item_name",
		"custom_excel_version",
		"custom_excel_applicable_model",
		"custom_excel_item_group",
		"custom_excel_total_amount",
		"custom_excel_source_qty",
		"custom_excel_delivery_note",
		"custom_excel_purchase_order",
		"custom_excel_warehouse",
		"custom_excel_source_row",
	),
	"Purchase Order": (
		"custom_purchase_comparison", "custom_excel_category", "custom_excel_order_no",
		"custom_excel_total_amount", "custom_excel_remarks", "custom_excel_source_file",
		"custom_excel_source_rows", "custom_excel_reconciliation_status",
		"custom_progress_milestone_code", "custom_progress_step_name", "custom_progress_actual_completed_on",
	),
	"Purchase Order Item": (
		"custom_excel_item_name", "custom_excel_amount", "custom_excel_tax_rate",
		"custom_excel_model", "custom_excel_order_qty", "custom_excel_delivered_qty",
		"custom_excel_undelivered_qty", "custom_excel_reconciled_qty",
		"custom_excel_delivery_1_qty", "custom_excel_delivery_1_date",
		"custom_excel_delivery_2_qty", "custom_excel_delivery_2_date",
		"custom_excel_delivery_3_qty", "custom_excel_delivery_3_date",
		"custom_excel_delivery_4_qty", "custom_excel_delivery_4_date",
		"custom_excel_delivery_5_qty", "custom_excel_delivery_5_date",
		"custom_excel_delivery_6_qty", "custom_excel_delivery_6_date",
		"custom_excel_delivery_7_qty", "custom_excel_delivery_7_date",
		"custom_excel_return_1_qty", "custom_excel_return_1_date",
		"custom_excel_return_2_qty", "custom_excel_return_2_date",
		"custom_excel_replenished_qty", "custom_excel_replenished_date",
		"custom_excel_pending_replenishment_qty", "custom_excel_item_remarks",
		"custom_excel_reconciliation_status", "custom_excel_source_row",
	),
	"Buying Settings": (
		"custom_supplier_quotation_warehouse",
		"custom_misc_purchase_item",
		"custom_rating_enabled",
		"custom_rating_rating_frequency",
		"custom_rating_evaluation_period_months",
		"custom_rating_weight_on_time",
		"custom_rating_delay_zero_score_days",
		"custom_rating_grade_a_min",
	),
	"Stock Settings": ("custom_customer_loan_warehouse",),
	"BOM": (
		"custom_bom_code",
		"custom_bom_structure",
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Sales Invoice": ("custom_progress_milestone_code", "custom_progress_step_name", "custom_progress_actual_completed_on"),
	"Purchase Invoice": ("custom_progress_milestone_code", "custom_progress_step_name", "custom_progress_actual_completed_on", "custom_purchase_follow_up"),
	"BOM Item": (
		"custom_import_level",
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	),
	"Material Request": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
		"custom_progress_project",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Work Order": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
		"custom_progress_milestone_code",
		"custom_progress_step_name",
		"custom_progress_actual_completed_on",
	),
	"Project": (
		"custom_technical_domain",
		"custom_project_leader",
		"custom_project_cost_details_section",
		"custom_project_cost_details",
		"custom_project_cost_detail_total",
		"custom_project_application_section",
		"custom_application_date",
		"custom_product_attr_proofing",
		"custom_product_attr_refurbished",
		"custom_product_attr_new",
		"custom_product_attr_other",
		"custom_replaced_customer_product",
		"custom_optical_parameters_section",
		"custom_magnification",
		"custom_working_distance",
		"custom_resolution",
		"custom_oi_distance",
		"custom_tv_distortion",
		"custom_business_impact",
		"custom_project_budget_total",
		"custom_department_manager",
		"custom_project_leader_sign_date",
		"custom_department_manager_sign_date",
		"custom_project_files_tab",
		"custom_project_files_section",
		"custom_project_files_html",
		"custom_project_files",
		"custom_project_budget_section",
		"custom_project_budget_details",
		"custom_project_standard_fields_section",
		"custom_progress_section",
		"custom_project_stage",
		"custom_progress_template",
		"custom_expected_progress",
		"custom_actual_process_progress",
		"custom_progress_variance",
		"custom_progress_health",
		"custom_current_progress_step",
		"custom_current_progress_duration",
		"custom_progress_last_synced_on",
		"custom_project_progress_items",
	),
	"Timesheet Detail": ("custom_work_order", "custom_excel_date", "custom_excel_total_hours"),
	"Asset": (
		"custom_asset_code",
		"custom_national_asset_classification_code",
		"custom_asset_specification",
		"custom_asset_serial_no",
		"custom_asset_depreciation_years",
		"custom_asset_monthly_depreciation",
		"custom_asset_department",
		"custom_asset_custodian",
		"custom_asset_status",
		"custom_asset_remarks",
	),
	"Customer": (
		"custom_responsible_sales_person",
		"custom_responsible_business_name",
		"custom_excel_contact_name",
		"custom_excel_contact_phone",
		"custom_excel_address",
	),
}


def sync_standard_custom_fields():
	"""Restore every standard-DocType Custom Field owned by this app."""
	from client_akivision.utils.item_product_identity import ensure_schema as ensure_item_product_identity_schema
	ensure_item_product_identity_schema()
	from client_akivision.patches.v0_0_1 import (
		add_buying_settings_supplier_quotation_warehouse,
		add_engineering_drawing_custom_fields,
		add_item_product_status_and_remarks,
		add_project_custom_fields,
		add_purchase_comparison_po_link,
		add_purchase_receipt_po_link,
		add_safety_stock_custom_fields,
		add_sales_order_delivery_note_remarks,
		add_sales_order_high_tech_field,
	add_sample_loan_in_custom_fields,
		add_sample_management_custom_fields,
		add_supplier_quote_column_mapping_field,
		add_supplier_quote_item_mapping_field,
		add_supplier_rating_field,
		add_supplier_rating_standard_field,
		add_rating_settings_to_buying_settings,
		ensure_item_report_fields,
	)
	from client_akivision.utils.purchase_order_drawing import ensure_schema as ensure_purchase_order_drawing_schema
	from client_akivision.utils.purchase_order_tracking import ensure_schema as ensure_purchase_order_tracking_schema
	from client_akivision.utils.bom import ensure_schema as ensure_bom_schema
	from client_akivision.utils.project_cost import ensure_schema as ensure_project_cost_schema
	from client_akivision.utils.project_development_application import ensure_schema as ensure_project_development_application_schema
	from client_akivision.utils.project_progress import ensure_schema as ensure_project_progress_schema

	ensure_item_report_fields.execute()
	add_item_product_status_and_remarks.execute()
	add_supplier_quote_column_mapping_field.execute()
	add_supplier_quote_item_mapping_field.execute()
	add_buying_settings_supplier_quotation_warehouse.execute()
	ensure_misc_purchase_item_field()
	ensure_customer_loan_warehouse_field()
	add_safety_stock_custom_fields.create_item_reorder_custom_fields()
	add_safety_stock_custom_fields.create_item_custom_fields()
	add_sales_order_high_tech_field.create_sales_order_custom_fields()
	add_sales_order_delivery_note_remarks.execute()
	add_project_custom_fields.execute()
	add_purchase_receipt_po_link.execute()
	add_purchase_comparison_po_link.execute()
	add_engineering_drawing_custom_fields.execute()
	add_supplier_rating_field.execute()
	add_supplier_rating_standard_field.execute()
	add_rating_settings_to_buying_settings.execute()
	add_sample_management_custom_fields.create_item_custom_fields()
	add_sample_management_custom_fields.create_serial_no_custom_fields()
	add_sample_management_custom_fields.create_stock_entry_custom_fields()
	add_sample_loan_in_custom_fields.create_serial_no_custom_fields()
	ensure_user_title_field_in_link()
	ensure_manual_batch_field()
	ensure_purchase_order_drawing_schema()
	ensure_purchase_order_tracking_schema()
	ensure_bom_schema()
	ensure_project_cost_schema()
	ensure_project_development_application_schema()
	ensure_project_progress_schema()
	ensure_purchase_follow_up_field()
	ensure_excel_form_fields()
	ensure_customer_salesperson_layout()
	# Customer links store the customer document name and display its human-
	# readable customer name. Business codes are exposed in dedicated fields.
	if frappe.db.exists("DocType", "Customer") and frappe.get_meta("Customer").get_field("custom_customer_code"):
		frappe.db.set_value("DocType", "Customer", "title_field", "customer_name", update_modified=False)
		frappe.db.set_value("DocType", "Customer", "show_title_field_in_link", 1, update_modified=False)
		frappe.clear_cache(doctype="Customer")

	for doctype in REQUIRED_FIELDS:
		if frappe.db.exists("Custom Field", {"dt": doctype}):
			frappe.db.updatedb(doctype)
			frappe.clear_cache(doctype=doctype)

	validate_standard_custom_fields()
	# Keep the presentation registry in the migration audit trail without
	# making an optional report/doctype block the whole site migration.
	from client_akivision.utils import excel_record_presentation

	presentation_issues = excel_record_presentation.audit_presentation_config()
	if presentation_issues:
		frappe.logger("client_akivision").warning(
			f"Excel presentation registry has issues: {frappe.as_json(presentation_issues)}"
		)


def ensure_user_title_field_in_link():
	"""Show User.full_name when a User is selected in Link fields.

	User.name is the login email and remains the stored value. Enabling this
	DocType option makes Frappe render the configured title field instead.
	"""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	property_setter = next(
		(
			row.name
			for row in frappe.get_all(
				"Property Setter",
				filters={"doc_type": "User", "property": "show_title_field_in_link"},
				fields=["name", "field_name", "doctype_or_field"],
			)
			if not row.field_name and row.doctype_or_field == "DocType"
		),
		None,
	)
	if property_setter:
		if str(frappe.db.get_value("Property Setter", property_setter, "value")) != "1":
			frappe.db.set_value("Property Setter", property_setter, "value", "1", update_modified=False)
	else:
		make_property_setter(
			"User",
			None,
			"show_title_field_in_link",
			"1",
			"Check",
			for_doctype=True,
			is_system_generated=False,
		)
	frappe.clear_cache(doctype="User")


def ensure_manual_batch_field():
	if frappe.db.exists("Custom Field", {"dt": "Stock Entry Detail", "fieldname": "custom_manual_batch_no"}):
		return
	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "Stock Entry Detail",
		"fieldname": "custom_manual_batch_no",
		"label": "手动填写批号",
		"fieldtype": "Data",
		"insert_after": "batch_no",
		"description": "提交入库类物料移动时自动创建或复用该批号。",
	}).insert(ignore_permissions=True)


def sync_customer_excel_import_text_fields():
 	"""Create only the Customer text fields needed by the Excel customer import."""
 	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

 	create_custom_fields({
 		"Customer": [
 			{
 				"fieldname": "custom_excel_contact_name",
 				"label": "联系人",
 				"fieldtype": "Data",
 				"insert_after": "customer_name",
 				"description": "Excel 客户清单的联系人原始文本；导入时不要求 Contact 预先存在。",
 				"in_list_view": 1,
 			},
 			{
 				"fieldname": "custom_excel_contact_phone",
 				"label": "联系电话",
 				"fieldtype": "Data",
 				"insert_after": "custom_excel_contact_name",
 				"description": "Excel 客户清单的联系电话原始文本；正式联系人电话由关联补全逻辑维护。",
 				"in_list_view": 1,
 			},
 			{
 				"fieldname": "custom_excel_address",
 				"label": "地址",
 				"fieldtype": "Small Text",
 				"insert_after": "custom_excel_contact_phone",
 				"description": "Excel 客户清单的地址原始文本；正式 Address 由关联补全逻辑维护。",
 				"in_list_view": 1,
 			},
 		]
 	}, update=True)
 	frappe.db.updatedb("Customer")
 	frappe.clear_cache(doctype="Customer")
 	return {
 		fieldname: frappe.db.exists("Custom Field", {"dt": "Customer", "fieldname": fieldname})
 		for fieldname in ("custom_excel_contact_name", "custom_excel_contact_phone", "custom_excel_address")
 	}


def ensure_excel_form_fields():
	"""Sync Excel-owned fields and form properties from JSON."""
	import json

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	path = frappe.get_app_path("client_akivision", "config", "excel_form_fields.json")
	with open(path, encoding="utf-8") as source:
		schema = json.load(source)

	create_custom_fields(schema["custom_fields"], update=True)

	errors = []
	for setter in schema.get("property_setters", []):
		field = frappe.get_meta(setter["doctype"]).get_field(setter["fieldname"])
		if not field:
			errors.append(f'{setter["doctype"]}.{setter["fieldname"]} is missing')
			continue
		existing = frappe.db.get_value(
			"Property Setter",
			{
				"doc_type": setter["doctype"],
				"field_name": setter["fieldname"],
				"property": setter["property"],
			},
			["value", "property_type"],
			as_dict=True,
		)
		if (
			existing
			and str(existing.value) == str(setter["value"])
			and existing.property_type == setter["property_type"]
		):
			continue
		make_property_setter(
			setter["doctype"],
			setter["fieldname"],
			setter["property"],
			setter["value"],
			setter["property_type"],
			is_system_generated=False,
		)

	for doctype, fields in schema["custom_fields"].items():
		meta = frappe.get_meta(doctype)
		for definition in fields:
			field = meta.get_field(definition["fieldname"])
			if not field:
				errors.append(f'{doctype}.{definition["fieldname"]} was not created')
				continue
			if definition["fieldtype"] != field.fieldtype:
				errors.append(f'{doctype}.{definition["fieldname"]} has type {field.fieldtype}, expected {definition["fieldtype"]}')
			if definition.get("options") and field.options != definition["options"]:
				errors.append(f'{doctype}.{definition["fieldname"]} links to {field.options}, expected {definition["options"]}')
			if definition.get("fetch_from") and field.fetch_from != definition["fetch_from"]:
				errors.append(f'{doctype}.{definition["fieldname"]} fetches from {field.fetch_from}, expected {definition["fetch_from"]}')
			if definition.get("read_only") and not field.read_only:
				errors.append(f'{doctype}.{definition["fieldname"]} must be read-only')

	for link in schema["existing_links"]:
		field = frappe.get_meta(link["doctype"]).get_field(link["fieldname"])
		if not field:
			errors.append(f'{link["doctype"]}.{link["fieldname"]} is missing')
		elif field.fieldtype not in {"Link", "Dynamic Link"}:
			errors.append(f'{link["doctype"]}.{link["fieldname"]} is not a Link field')
		elif field.fieldtype == "Link" and field.options != link["options"]:
			errors.append(
				f'{link["doctype"]}.{link["fieldname"]} links to {field.options}, expected {link["options"]}'
			)

	if errors:
		frappe.throw("Excel form field link validation failed:\n" + "\n".join(errors))

	touched_doctypes = set(schema["custom_fields"])
	touched_doctypes.update(setter["doctype"] for setter in schema.get("property_setters", []))
	for doctype in touched_doctypes:
		frappe.db.updatedb(doctype)
		frappe.clear_cache(doctype=doctype)

	# ``custom_excel_*`` is retained as the stable storage/API name, but the
	# implementation detail should not leak into the user-facing form labels.
	# This also normalizes fields created by older patches that are not present
	# in excel_form_fields.json anymore.
	normalize_excel_field_labels()


def ensure_customer_salesperson_layout():
	"""Keep customer ownership in the details tab and simplify Sales Team."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	if not frappe.db.exists("DocType", "Customer"):
		return

	properties = (
		("account_manager", "hidden", "1", "Check"),
		("custom_responsible_business_name", "hidden", "1", "Check"),
		("sales_team", "hidden", "1", "Check"),
		("sales_team_section", "hidden", "1", "Check"),
		("default_sales_partner", "label", "业务人员（业务伙伴）", "Data"),
		("default_commission_rate", "label", "佣金率", "Data"),
	)
	meta = frappe.get_meta("Customer")
	for fieldname, property_name, value, property_type in properties:
		if not meta.get_field(fieldname):
			continue
		existing = frappe.db.get_value(
			"Property Setter",
			{"doc_type": "Customer", "field_name": fieldname, "property": property_name},
			"value",
		)
		if str(existing) == value:
			continue
		make_property_setter(
			"Customer", fieldname, property_name, value, property_type, is_system_generated=True
		)

	frappe.db.updatedb("Customer")
	frappe.clear_cache(doctype="Customer")


def normalize_excel_field_labels():
	"""Remove the import-source marker from visible custom field labels."""
	import re

	changed_doctypes = set()
	for row in frappe.get_all("Custom Field", fields=["name", "dt", "label"]):
		label = row.label or ""
		if "excel" not in label.lower():
			continue
		new_label = re.sub(r"(?i)\s*\(\s*excel\s*\)", "", label)
		new_label = re.sub(r"(?i)excel\s*", "", new_label).strip()
		if new_label and new_label != label:
			frappe.db.set_value("Custom Field", row.name, "label", new_label, update_modified=False)
			changed_doctypes.add(row.dt)
	for doctype in changed_doctypes:
		frappe.clear_cache(doctype=doctype)


def ensure_customer_loan_warehouse_field():
	"""Add the warehouse default used as the destination for customer sample loans."""
	if not frappe.db.exists("Custom Field", {"dt": "Stock Settings", "fieldname": "custom_customer_loan_warehouse"}):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Stock Settings",
			"fieldname": "custom_customer_loan_warehouse",
			"label": "客户借出仓库",
			"fieldtype": "Link",
			"options": "Warehouse",
			"insert_after": "sample_retention_warehouse",
			"description": "样品借出时作为调拨目的仓库。",
		}).insert(ignore_permissions=True)


def ensure_misc_purchase_item_field():
	"""Add the configurable carrier item used by miscellaneous purchases."""
	if frappe.db.exists("Custom Field", {"dt": "Buying Settings", "fieldname": "custom_misc_purchase_item"}):
		return
	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "Buying Settings",
		"fieldname": "custom_misc_purchase_item",
		"label": "零星采购物料",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_supplier_quotation_warehouse",
		"description": "零星采购发票使用的通用物料载体。",
	}).insert(ignore_permissions=True)


def ensure_purchase_follow_up_field():
	"""Link draft purchase invoices back to the supplier reconciliation record."""
	if not frappe.db.exists("DocType", "Purchase Invoice") or not frappe.db.exists("DocType", "Purchase Follow Up"):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields({
		"Purchase Invoice": [{
			"fieldname": "custom_purchase_follow_up",
			"label": "采购跟进单",
			"fieldtype": "Link",
			"options": "Purchase Follow Up",
			"insert_after": "supplier",
		}],
	}, update=True)
	frappe.db.updatedb("Purchase Invoice")


def validate_standard_custom_fields():
	missing = []
	for doctype, fieldnames in REQUIRED_FIELDS.items():
		if not frappe.db.exists("DocType", doctype):
			missing.extend(f"{doctype}.{fieldname} (DocType missing)" for fieldname in fieldnames)
			continue
		meta = frappe.get_meta(doctype)
		for fieldname in fieldnames:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
				missing.append(f"{doctype}.{fieldname} (Custom Field)")
			elif (
				fieldname
				and not meta.issingle
				and meta.get_field(fieldname).fieldtype not in NO_VALUE_FIELDS
				and not frappe.db.has_column(doctype, fieldname)
			):
				missing.append(f"{doctype}.{fieldname} (database column)")

	if missing:
		frappe.throw("Missing client_akivision schema:\n" + "\n".join(missing))
