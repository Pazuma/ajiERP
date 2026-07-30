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
	"Stock Entry Detail": ("custom_manual_batch_no",),
	"Supplier": ("custom_supplier_rating", "custom_quote_column_mapping", "custom_quote_item_mapping"),
	"Sales Order": ("custom_is_high_tech_revenue", "custom_remarks"),
	"Delivery Note": ("custom_remarks",),
	"Purchase Receipt": ("custom_purchase_order",),
	"Purchase Order": ("custom_purchase_comparison",),
	"Supplier Quotation": ("custom_tier_sync_status",),
	"Buying Settings": ("custom_supplier_quotation_warehouse", "custom_misc_purchase_item"),
	"Stock Settings": ("custom_customer_loan_warehouse",),
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
		add_supplier_quotation_tier_sync_field,
		add_supplier_rating_field,
		ensure_item_report_fields,
	)
	from client_akivision.utils.purchase_order_drawing import ensure_schema as ensure_purchase_order_drawing_schema

	ensure_item_report_fields.execute()
	add_item_product_status_and_remarks.execute()
	add_supplier_quote_column_mapping_field.execute()
	add_supplier_quote_item_mapping_field.execute()
	add_supplier_quotation_tier_sync_field.execute()
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
	add_sample_management_custom_fields.create_item_custom_fields()
	add_sample_management_custom_fields.create_serial_no_custom_fields()
	add_sample_management_custom_fields.create_stock_entry_custom_fields()
	add_sample_loan_in_custom_fields.create_serial_no_custom_fields()
	ensure_manual_batch_field()
	ensure_purchase_order_drawing_schema()

	for doctype in REQUIRED_FIELDS:
		if frappe.db.exists("Custom Field", {"dt": doctype}):
			frappe.db.updatedb(doctype)
			frappe.clear_cache(doctype=doctype)

	validate_standard_custom_fields()


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
	frappe.db.set_single_value("Buying Settings", "custom_misc_purchase_item", "MISC-PURCHASE")


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
			elif not meta.issingle and not frappe.db.has_column(doctype, fieldname):
				missing.append(f"{doctype}.{fieldname} (database column)")

	if missing:
		frappe.throw("Missing client_akivision schema:\n" + "\n".join(missing))
