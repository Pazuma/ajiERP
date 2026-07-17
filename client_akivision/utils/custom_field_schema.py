import frappe


REQUIRED_FIELDS = {
	"Item": (
		"custom_internal_model",
		"custom_external_model",
		"custom_applicable_model",
		"custom_version",
		"custom_product_status",
		"custom_remarks",
		"custom_safety_stock_remarks",
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
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
		"custom_akivision_sample_loan_doctype",
		"custom_akivision_sample_loan_doc",
	),
	"Supplier": ("custom_supplier_rating", "custom_quote_column_mapping", "custom_quote_item_mapping"),
	"Sales Order": ("custom_is_high_tech_revenue", "custom_remarks"),
	"Delivery Note": ("custom_remarks",),
	"Purchase Receipt": ("custom_purchase_order",),
	"BOM": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	),
	"BOM Item": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	),
	"Material Request": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	),
	"Work Order": (
		"custom_engineering_drawing",
		"custom_engineering_drawing_no",
		"custom_engineering_drawing_revision",
	),
	"Project": ("custom_technical_domain", "custom_project_leader"),
}


def sync_standard_custom_fields():
	"""Restore every standard-DocType Custom Field owned by this app."""
	from client_akivision.patches.v0_0_1 import (
		add_engineering_drawing_custom_fields,
		add_item_product_status_and_remarks,
		add_project_custom_fields,
		add_purchase_receipt_po_link,
		add_safety_stock_custom_fields,
		add_sales_order_delivery_note_remarks,
		add_sales_order_high_tech_field,
		add_sample_loan_in_custom_fields,
		add_sample_management_custom_fields,
		add_supplier_quote_column_mapping_field,
		add_supplier_quote_item_mapping_field,
		add_supplier_rating_field,
		ensure_item_report_fields,
	)

	ensure_item_report_fields.execute()
	add_item_product_status_and_remarks.execute()
	add_supplier_quote_column_mapping_field.execute()
	add_supplier_quote_item_mapping_field.execute()
	add_safety_stock_custom_fields.create_item_reorder_custom_fields()
	add_safety_stock_custom_fields.create_item_custom_fields()
	add_sales_order_high_tech_field.create_sales_order_custom_fields()
	add_sales_order_delivery_note_remarks.execute()
	add_project_custom_fields.execute()
	add_purchase_receipt_po_link.execute()
	add_engineering_drawing_custom_fields.execute()
	add_supplier_rating_field.execute()
	add_sample_management_custom_fields.create_item_custom_fields()
	add_sample_management_custom_fields.create_serial_no_custom_fields()
	add_sample_management_custom_fields.create_stock_entry_custom_fields()
	add_sample_loan_in_custom_fields.create_serial_no_custom_fields()

	for doctype in REQUIRED_FIELDS:
		if frappe.db.exists("Custom Field", {"dt": doctype}):
			frappe.db.updatedb(doctype)
			frappe.clear_cache(doctype=doctype)

	validate_standard_custom_fields()


def validate_standard_custom_fields():
	missing = []
	for doctype, fieldnames in REQUIRED_FIELDS.items():
		for fieldname in fieldnames:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
				missing.append(f"{doctype}.{fieldname} (Custom Field)")
			elif not frappe.db.has_column(doctype, fieldname):
				missing.append(f"{doctype}.{fieldname} (database column)")

	if missing:
		frappe.throw("Missing client_akivision schema:\n" + "\n".join(missing))
