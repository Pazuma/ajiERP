app_name = "client_akivision"
app_title = "Client Akivision"
app_publisher = "yuewei"
app_description = "akivision"
app_email = "akivision@example.com"
app_license = "mit"

# Render company branding in the initial HTML, before Desk JavaScript loads.
splash_image = "/assets/client_akivision/images/aki_vision_logo.png?v=2026110201"
favicon = "/assets/client_akivision/images/aki_sidebar_icon.svg?v=2026110402"
update_website_context = "client_akivision.utils.branding.update_context"

fixtures = [
	{"dt": "Custom Field", "filters": [["name", "=", "User-custom_department"]]},
]

# Apps
# ------------------

required_apps = ["erpnext", "custom_filters"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "client_akivision",
# 		"logo": "/assets/client_akivision/logo.png",
# 		"title": "Client Akivision",
# 		"route": "/client_akivision",
# 		"has_permission": "client_akivision.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/client_akivision/css/client_akivision.css"
app_include_js = [
	"/assets/client_akivision/js/customer_quick_entry.js?v=2026102902",
	"/assets/client_akivision/js/supplier_quick_entry.js?v=2026103002",
	"/assets/client_akivision/js/company_header_logo.js?v=2026102005",
	"/assets/client_akivision/js/toolbar_hover_dropdown.js?v=2026101301",
	"/assets/client_akivision/js/layered_shortage_dialog.js?v=2026101603",
	"/assets/client_akivision/js/stock_entry_shortage_dialog.js?v=2026101602",
	"/assets/client_akivision/js/item_module_context.js",
	"/assets/client_akivision/js/stock_settings_naming.js",
	"/assets/client_akivision/js/company_desktop_icons.js?v=2026110201",
	"/assets/client_akivision/js/desktop_icon_logo.js?v=2026110402",
	"/assets/client_akivision/js/sidebar_icons.js",
	"/assets/client_akivision/js/auto_fulfilment_badges.js",
	"/assets/client_akivision/js/project_progress_click_fix.js?v=2026091501",
	"/assets/client_akivision/js/project_list_stage.js?v=2026092904",
	"/assets/client_akivision/js/project_link_create_binding.js?v=2026091601",
	"/assets/client_akivision/js/inline_data_import.js",
	"/assets/client_akivision/js/zh_ui_translations.js?v=2026101602",
	"/assets/client_akivision/js/list_horizontal_scroll.js",
	"/assets/client_akivision/js/list_field_selector_search.js?v=2026092301",
]
app_include_css = [
	"/assets/client_akivision/css/company_login_logo.css?v=2026110202",
	"/assets/client_akivision/css/hide_fieldname_tooltips.css?v=2026102201",
	"/assets/client_akivision/css/company_header_logo.css?v=2026102009",
	"/assets/client_akivision/css/material_stocktake_summary.css?v=2026101501",
	"/assets/client_akivision/css/project_form_layout.css?v=2026102003",
	"/assets/client_akivision/css/purchase_order_form.css?v=2026101312",
	"/assets/client_akivision/css/stock_entry_form.css?v=2026101601",
	"/assets/client_akivision/css/purchase_return_form.css?v=2026101301",
	"/assets/client_akivision/css/data_import.css?v=2026102002",
	"/assets/client_akivision/css/sidebar_width.css?v=2026091401",
	"/assets/client_akivision/css/sidebar_section_titles.css?v=2026101501",
	"/assets/client_akivision/css/auto_fulfilment_badges.css",
	"/assets/client_akivision/css/auto_draft_read_badge.css",
	"/assets/client_akivision/css/project_files.css?v=2026092001",
	"/assets/client_akivision/css/sales_order_products.css?v=2026102102",
	"/assets/client_akivision/css/list_field_selector_search.css?v=2026092301",
	"/assets/client_akivision/css/white_form_controls.css?v=2026101301",
	"/assets/client_akivision/css/work_order_form.css?v=2026101604",
	"/assets/client_akivision/css/quality_inspection_layout.css?v=2026102301",
	"/assets/client_akivision/css/purchase_receipt_form_layout.css?v=2026110302",
]

# include js, css files in header of web template
web_include_css = "/assets/client_akivision/css/company_login_logo.css?v=2026110202"
# web_include_js = "/assets/client_akivision/js/client_akivision.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "client_akivision/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}
page_js = {"supplier-purchase-consolidation": "public/js/supplier_purchase_consolidation.js"}

# include js in doctype views
doctype_js = {
	"Payment Entry": "public/js/payment_entry_layout.js",
	"Company": "public/js/company.js",
	"Data Import": "public/js/data_import.js",
	"Supplier Scorecard": "public/js/supplier_scorecard.js",
	"Material Request": "public/js/material_request.js",
	"Work Order": "public/js/work_order.js",
	"Job Card": "public/js/job_card_layout.js",
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Purchase Order": ["public/js/purchase_order.js", "public/js/purchase_quality_flow.js"],
	"Quality Inspection": ["public/js/purchase_quality_flow.js", "public/js/quality_inspection_layout.js"],
	"BOM": "public/js/bom.js",
	"Sales Order": "public/js/sales_order_delivery.js",
	"Delivery Note": "public/js/delivery_note.js",
	"Customer": "public/js/customer.js",
	"Stock Entry": "public/js/stock_entry_labor.js",
	"Purchase Receipt": "public/js/purchase_receipt_quality_gate.js",
	"Engineering Drawing": "public/js/engineering_drawing.js",
	"KPI Metric Definition": "public/js/kpi_metric_definition.js",
	"Project": ["public/js/project_cost_detail.js", "public/js/project_progress.js", "public/js/project_files.js", "public/js/project_development_application_visibility.js"],
	"Timesheet": "public/js/timesheet_hide_company_customer.js?v=2026102101",
}
for _project_progress_doctype in (
	"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
	"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
):
	_existing_scripts = doctype_js.get(_project_progress_doctype)
	if not _existing_scripts:
		doctype_js[_project_progress_doctype] = "public/js/project_progress_reference.js"
	elif isinstance(_existing_scripts, list):
		_existing_scripts.append("public/js/project_progress_reference.js")
	else:
		doctype_js[_project_progress_doctype] = [_existing_scripts, "public/js/project_progress_reference.js"]
for _estimated_cost_doctype in ("BOM", "Work Order"):
	doctype_js[_estimated_cost_doctype].append("public/js/estimated_material_cost.js")
_item_scripts = doctype_js.get("Item", [])
_item_scripts = [_item_scripts] if isinstance(_item_scripts, str) else list(_item_scripts)
doctype_js["Item"] = _item_scripts + ["public/js/item_purchase_average.js", "public/js/sales_product_stock.js", "public/js/item_role_view.js", "public/js/item_form_layout.js"]
doctype_js["Sales Order"].append("public/js/sales_product_stock.js")
doctype_js["Sales Order"].append("public/js/sales_order_export.js")
doctype_list_js = {
	"UOM": "public/js/uom_list.js",
	"Material Request": "public/js/material_request_list.js",
	"Purchase Order": "public/js/purchase_order_list.js",
	"Delivery Note": ["public/js/delivery_note_list.js", "public/js/auto_draft_read_badge.js"],
	"Supplier": "public/js/supplier_list.js",
	"Customer": "public/js/customer_list.js",
	"Finished Goods Status": "public/js/finished_goods_status_list.js",
	"Stock Entry": "public/js/document_export_list.js",
	"Material Stocktake Summary": "public/js/document_export_list.js",
	"Work Order": ["public/js/document_export_list.js", "public/js/auto_draft_read_badge.js"],
	"Purchase Receipt": "public/js/document_export_list.js",
	"Item": ["public/js/document_export_list.js", "public/js/sales_product_item_list.js"],
	"Project": "public/js/document_export_list.js",
	"Sales Order": ["public/js/document_export_list.js", "public/js/sales_order_products_list.js"],
	"Price List": "public/js/document_export_list.js",
	"Asset": "public/js/document_export_list.js",
	"BOM": ["public/js/document_export_list.js", "public/js/bom_list.js"],
	"Timesheet": "public/js/document_export_list.js",
}

doctype_css = {
	"Sales Order": "public/css/sales_order_products.css",
}

for _auto_draft_doctype in ("Delivery Note", "Work Order", "China Sales Settlement", "Purchase Follow Up"):
	_scripts = doctype_js.get(_auto_draft_doctype, [])
	_scripts = [_scripts] if isinstance(_scripts, str) else list(_scripts)
	doctype_js[_auto_draft_doctype] = _scripts + ["public/js/auto_draft_form_read.js"]
	if _auto_draft_doctype not in ("Delivery Note", "Work Order"):
		doctype_list_js[_auto_draft_doctype] = "public/js/auto_draft_read_badge.js"

# Keep the Selling workspace configuration in the database, but limit what is
# returned in the sidebar payload sent to desk users.
boot_session = ["client_akivision.utils.workspace_sidebar.hide_selling_pos_and_non_delivery_reports",
	"client_akivision.utils.branding.apply_boot_branding",
	"client_akivision.utils.product_cost_navigation.configure_entries",
	"client_akivision.utils.custom_module_navigation.configure_entries"]

# Separate costing branches; preserve every existing form script and API.
for _pcq_doctype in ("Item", "Project", "Work Order"):
	_pcq_scripts = doctype_js.get(_pcq_doctype, [])
	_pcq_scripts = [_pcq_scripts] if isinstance(_pcq_scripts, str) else list(_pcq_scripts)
	doctype_js[_pcq_doctype] = _pcq_scripts + ["public/js/product_cost_entry.js"]
doctype_js["Sales Order"].append("public/js/sales_order_cost_quote.js")
after_migrate = [
	"client_akivision.utils.sample_loan_settings.ensure_schema",
	"client_akivision.utils.custom_module_navigation.ensure_schema",
	"client_akivision.utils.supplier_fields.ensure_schema",
	"client_akivision.utils.uom_chinese_labels.ensure_chinese_labels",
	"client_akivision.utils.uom_chinese_labels.ensure_item_code_naming",
	"client_akivision.utils.supplier_layout.ensure_layout",
	"client_akivision.utils.supplier_excel_import.ensure_schema",
	"client_akivision.utils.layered_manufacturing.ensure_schema",
	"client_akivision.utils.item_module_view.ensure_schema",
	"client_akivision.utils.delivery_trip_express.ensure_schema",
	"client_akivision.utils.custom_field_schema.sync_standard_custom_fields",
	"client_akivision.utils.purchase_order_fields.ensure_schema",
	"client_akivision.utils.item_product_identity.ensure_schema",
	"client_akivision.utils.item_categories.sync_item_categories",
	"client_akivision.utils.sales_order_product_cost.ensure_schema",
	"client_akivision.utils.item_product_identity.ensure_sales_product_permissions",
	"client_akivision.utils.item_purchase_average.ensure_schema",
	"client_akivision.utils.stock_entry_types.sync_stock_entry_types",
	"client_akivision.utils.deployment_defaults.sync_deployment_defaults",
	"client_akivision.utils.misc_purchase.sync_misc_purchase_item_name",
	"client_akivision.utils.operations_management.sync_operations_management_desktop_icon",
	"client_akivision.utils.master_data_sidebar.sync_master_data_sidebar",
	"client_akivision.utils.branding.sync_login_logo",
	"client_akivision.utils.selling_sidebar.sync_selling_sidebar_entries",
	"client_akivision.utils.selling_sidebar.hide_selling_item_entry",
	"client_akivision.utils.selling_sidebar.persist_selling_groups",
	"client_akivision.utils.buying_sidebar.sync_buying_sidebar_entries",
	"client_akivision.utils.stock_sidebar.sync_stock_sidebar_entries",
	"client_akivision.utils.report_sidebar.sync_report_sidebar_entries",
	"client_akivision.utils.manufacturing_sidebar.sync_manufacturing_sidebar_entries",
	"client_akivision.utils.quality_sidebar.sync_quality_sidebar_entries",
	"client_akivision.utils.accounts_setup_sidebar.sync_accounts_setup_sidebar_entries",
	"client_akivision.utils.project_progress.ensure_schema",
	"client_akivision.utils.other_forms_sidebar.sync_other_forms_sidebar_entries",
	"client_akivision.utils.misc_purchase.ensure_schema",
	"client_akivision.utils.supplier_fields.ensure_schema",
	"client_akivision.utils.selling_dashboard_metrics.ensure_selling_dashboard_cards",
	"client_akivision.utils.buying_dashboard_metrics.ensure_buying_dashboard_chart",
	"client_akivision.utils.manufacturing_dashboard_metrics.ensure_manufacturing_dashboard_cards",
	"client_akivision.utils.manufacturing_dashboard_layout.ensure_manufacturing_dashboard_chart_widths",
	"client_akivision.utils.timesheet_fields.hide_legacy_timesheet_fields",
	"client_akivision.utils.sales_order_list_fields.ensure_sales_order_list_fields",
	"client_akivision.utils.item_list_fields.ensure_item_list_fields",
	"client_akivision.utils.sales_order_fields.backfill_sales_order_period_fields",
	"client_akivision.utils.sales_order_fields.ensure_sales_order_layout",
	"client_akivision.utils.work_order_labor.ensure_schema",
	"client_akivision.utils.supplier_purchase_consolidation.ensure_schema",
	"client_akivision.utils.sales_order_production_cost.ensure_schema",
	"client_akivision.utils.manufacture_quality_gate.ensure_schema",
	"client_akivision.utils.purchase_order_drawing.ensure_schema",
	"client_akivision.utils.purchase_order_tracking.ensure_schema",
	"client_akivision.utils.purchase_quality_flow.ensure_schema",
	"client_akivision.utils.quality_inspection_layout.ensure_layout",
	"client_akivision.utils.purchase_order_payment_flow.ensure_schema",
	"client_akivision.utils.bom.ensure_schema",
	"client_akivision.utils.bom_version.ensure_schema",
	"client_akivision.utils.project_cost.ensure_schema",
	"client_akivision.utils.project_permissions.ensure_schema",
	"client_akivision.utils.project_development_application.ensure_schema",
	"client_akivision.client_akivision.doctype.material_stocktake_summary.material_stocktake_summary.ensure_stocktake_difference_reasons",
	"client_akivision.utils.inventory_impairment.ensure_schema",
	"client_akivision.utils.sales_product_field_permissions.ensure_schema",
]

override_doctype_class = {
	"Quality Inspection": "client_akivision.overrides.quality_inspection.WorkOrderQualityInspection",
	"Delivery Trip": "client_akivision.overrides.delivery_trip.ExpressDeliveryTrip",
	"Purchase Receipt": "client_akivision.overrides.purchase_receipt.QualityCheckedPurchaseReceipt",
	"Supplier": "client_akivision.overrides.supplier.ManuallyNumberedSupplier",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "client_akivision/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "client_akivision.utils.jinja_methods",
# 	"filters": "client_akivision.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "client_akivision.install.before_install"
# after_install = "client_akivision.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "client_akivision.uninstall.before_uninstall"
# after_uninstall = "client_akivision.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "client_akivision.utils.before_app_install"
# after_app_install = "client_akivision.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "client_akivision.utils.before_app_uninstall"
# after_app_uninstall = "client_akivision.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "client_akivision.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "client_akivision.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Item": "client_akivision.utils.item_product_identity.sales_item_query_conditions",
	"Item Price": "client_akivision.utils.item_product_identity.sales_price_query_conditions",
	"Sales Order": "client_akivision.utils.order_record_permissions.permission_query_conditions",
	"Purchase Order": "client_akivision.utils.order_record_permissions.permission_query_conditions",
	"Project": "client_akivision.utils.project_permissions.project_permission_query",
}
# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
has_permission = {
	"Product Cost Quotation": "client_akivision.utils.product_cost_permissions.has_permission",
	"Item": "client_akivision.utils.item_product_identity.sales_item_has_permission",
	"Item Price": "client_akivision.utils.item_product_identity.sales_price_has_permission",
	"Sales Order": "client_akivision.utils.order_record_permissions.sales_order_has_permission",
	"Purchase Order": "client_akivision.utils.order_record_permissions.purchase_order_has_permission",
	"Project": "client_akivision.utils.project_permissions.project_has_permission",
}
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Customer": {"after_insert": "client_akivision.utils.quick_party_entry.after_customer_insert"},
	"Supplier": {"after_insert": "client_akivision.utils.quick_party_entry.after_supplier_insert"},
	"User": {"onload": "client_akivision.utils.custom_module_navigation.add_module_options"},
	"Item": {
		"before_validate": "client_akivision.utils.item_product_identity.validate_item_product_identity",
		"validate": "client_akivision.utils.inventory_impairment.assess_item",
	},
	"Contact": {
		"before_validate": "client_akivision.utils.contact.ensure_primary_contact_numbers",
	},
	"Stock Entry": {
		"before_submit": "client_akivision.utils.layered_manufacturing.before_submit_stock_entry",
		"before_validate": [
			"client_akivision.utils.stock_entry_types.apply_stock_entry_reason",
			"client_akivision.utils.stock_entry_batch.ensure_inward_batches",
		],
		"validate": [
			"client_akivision.utils.layered_manufacturing.validate_stock_entry",
			"client_akivision.utils.stock_entry_labor.apply_work_order_labor_cost",
			"client_akivision.utils.sales_order_production_cost.set_stock_entry_sales_order",
		],
		"on_submit": [
			"client_akivision.utils.sample_loan.on_stock_entry_submit",
			"client_akivision.utils.sample_loan.on_stock_entry_submit_for_fgs",
			"client_akivision.utils.production_reorder.on_production_stock_entry_submit",
			"client_akivision.utils.work_order_completion.sync_work_order_after_manufacture_entry",
			"client_akivision.utils.sales_order_production_cost.refresh_from_stock_entry",
		],
		"on_cancel": [
			"client_akivision.utils.sample_loan.on_stock_entry_cancel",
			"client_akivision.utils.work_order_completion.sync_work_order_after_manufacture_entry",
			"client_akivision.utils.sales_order_production_cost.refresh_from_stock_entry",
		],
	},
	"Purchase Receipt": {
		"before_cancel": "client_akivision.utils.purchase_order_payment_flow.prevent_cancel_reconciled_receipt",
		"on_submit": [
			"client_akivision.utils.sample_loan.on_purchase_receipt_submit",
			"client_akivision.utils.purchase_quality_flow.update_receiving_notice_status",
			"client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		],
		"on_cancel": [
			"client_akivision.utils.purchase_quality_flow.update_receiving_notice_status",
			"client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		],
		"validate": [
			"client_akivision.utils.purchase_receipt.set_purchase_order_from_items",
		],
	},
	"Purchase Follow Up": {
		"before_cancel": "client_akivision.utils.purchase_order_payment_flow.prevent_cancel_invoiced_reconciliation",
		"on_submit": "client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		"on_cancel": "client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
	},
	"Payment Entry": {
		"on_submit": "client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		"on_cancel": "client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
	},
	"Quality Inspection": {
		"validate": [
			"client_akivision.utils.purchase_quality_flow.validate_purchase_order_source",
			"client_akivision.utils.manufacture_quality_gate.validate_quality_inspection",
		],
	},
	"Purchase Order": {
		"before_validate": [
			"client_akivision.utils.purchase_order_drawing.sync_drawings",
			"client_akivision.utils.purchase_order_fields.set_and_validate_procurement_specialist",
		],
		"validate": "client_akivision.utils.purchase_order_tracking.validate_delivery_plans",
		"on_submit": [
			"client_akivision.utils.supplier_purchase_consolidation.sync_purchase_order_sources",
			"client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		],
		"on_cancel": "client_akivision.utils.supplier_purchase_consolidation.sync_purchase_order_sources",
		"on_trash": "client_akivision.utils.supplier_purchase_consolidation.sync_purchase_order_sources",
	},
	"Supplier Scorecard": {
		"on_update": "client_akivision.utils.supplier_scorecard.update_supplier_rating",
	},
	"Supplier Scorecard Period": {
		"on_submit": "client_akivision.utils.supplier_scorecard.refresh_supplier_rating_from_period",
		"on_cancel": "client_akivision.utils.supplier_scorecard.refresh_supplier_rating_from_period",
	},
	"BOM": {
		"validate": ["client_akivision.utils.engineering_drawing.validate_bom_drawing", "client_akivision.utils.bom_version.validate_version"],
		"before_submit": "client_akivision.utils.bom_version.before_submit",
		"on_submit": "client_akivision.utils.bom_version.record_activation",
		"before_cancel": "client_akivision.utils.bom_version.before_cancel",
		"on_cancel": "client_akivision.utils.bom_version.on_cancel",
	},
	"Material Request": {
		"validate": [
			"client_akivision.utils.engineering_drawing.set_material_request_drawing_reference",
			"client_akivision.utils.misc_purchase.validate_misc_purchase_request",
		],
	},
	"Purchase Invoice": {
		"before_submit": "client_akivision.utils.purchase_order_payment_flow.validate_invoice_reconciliation",
		"on_update_after_submit": "client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		"on_submit": [
			"client_akivision.utils.misc_purchase.mark_request_completed_on_invoice_submit",
			"client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		],
		"on_update": "client_akivision.utils.misc_purchase.sync_misc_purchase_request_links",
		"on_cancel": [
			"client_akivision.utils.misc_purchase.reset_request_after_invoice_removed",
			"client_akivision.utils.purchase_order_payment_flow.sync_purchase_order_flow",
		],
		"on_trash": "client_akivision.utils.misc_purchase.reset_request_after_invoice_removed",
	},
	"Work Order": {
		"before_validate": "client_akivision.utils.layered_manufacturing.initialize_direct_component_work_order",
		"validate": [
			"client_akivision.utils.layered_manufacturing.validate_work_order",
			"client_akivision.utils.engineering_drawing.set_work_order_drawing_reference",
			"client_akivision.utils.work_order_labor.calculate_labor_cost",
			"client_akivision.utils.sales_order_production_cost.validate_work_order_loss",
		],
	},
	"Job Card": {
		"validate": "client_akivision.utils.sales_order_production_cost.validate_job_card_loss",
	},
	"Delivery Note": {
		"on_submit": "client_akivision.utils.sales_order_production_cost.refresh_from_delivery_note",
		"on_cancel": "client_akivision.utils.sales_order_production_cost.refresh_from_delivery_note",
	},
	"Project": {
		"before_insert": "client_akivision.utils.project_number.assign_project_number",
		"validate": [
			"client_akivision.utils.project_permissions.validate_project_finance_access",
			"client_akivision.utils.project_cost.validate_project_cost_details",
			"client_akivision.utils.project_development_application.validate_project_application",
			"client_akivision.utils.project_progress.validate_project_progress",
			"client_akivision.utils.project_files.validate_project_files",
		],
		"before_print": "client_akivision.utils.project_permissions.filter_project_print_fields",
		"on_update": [
			"client_akivision.utils.project_files.log_project_file_changes",
			"client_akivision.utils.project_permissions._sync_auto_members",
		],
	},
	"Sales Order": {
		"before_validate": [
			"client_akivision.utils.sales_order_fields.enforce_tax_inclusive_sales_pricing",
			"client_akivision.utils.sales_order_fields.sync_sales_order_period",
			"client_akivision.utils.sales_order_fields.sync_customer_code",
			"client_akivision.utils.sales_order_fields.sync_customer_sales_person",
			"client_akivision.utils.sales_order_fields.enforce_current_user_sales_person",
		],
		"before_submit": "client_akivision.utils.sales_order_fields.validate_customer_sales_person",
		"validate": "client_akivision.utils.sales_order_product_cost.validate_quote_snapshots",
		"on_update": "client_akivision.utils.sales_order_product_cost.save_quote_snapshots",
		"on_submit": "client_akivision.utils.sales_order_auto_fulfilment.enqueue_on_submit",
	},
	"Supplier": {
		"before_insert": "client_akivision.utils.supplier.use_imported_supplier_code_as_name",
		"after_insert": "client_akivision.utils.supplier_scorecard.create_supplier_scorecard",
	},
}

for _project_progress_doctype in (
	"Sales Order", "Purchase Order", "Material Request", "BOM", "Work Order",
	"Delivery Note", "Purchase Receipt", "Sales Invoice", "Purchase Invoice", "Stock Entry",
):
	_events = doc_events.setdefault(_project_progress_doctype, {})
	for _event_name, _progress_handler in (
		("validate", "client_akivision.utils.project_progress.validate_progress_selection"),
		("on_update", "client_akivision.utils.project_progress.sync_progress_selection"),
		("on_trash", "client_akivision.utils.project_progress.remove_progress_selection"),
	):
		_handler = _events.get(_event_name)
		if not _handler:
			_events[_event_name] = _progress_handler
		elif isinstance(_handler, list):
			_handler.append(_progress_handler)
		else:
			_events[_event_name] = [_handler, _progress_handler]
	for _event_name in ("on_submit", "on_cancel"):
		_handler = _events.get(_event_name)
		if not _handler:
			_events[_event_name] = "client_akivision.utils.project_progress.sync_progress_from_reference"
		elif isinstance(_handler, list):
			_handler.append("client_akivision.utils.project_progress.sync_progress_from_reference")
		else:
			_events[_event_name] = [_handler, "client_akivision.utils.project_progress.sync_progress_from_reference"]

# Scheduled Tasks
# New business-driven project mode observes downstream events without replacing
# any existing stock, accounting or legacy progress handlers.
for _business_dt in ("Purchase Order", "Work Order", "Sales Order", "Purchase Receipt", "Purchase Invoice", "Stock Entry", "Delivery Note", "Sales Invoice", "Quality Inspection", "Purchase Receiving Notice"):
	_business_events = doc_events.setdefault(_business_dt, {})
	for _business_event in ("on_update", "on_submit", "on_cancel", "on_update_after_submit", "on_trash"):
		_existing_business = _business_events.get(_business_event)
		_business_handler = "client_akivision.utils.project_progress_events.on_business_change"
		_business_events[_business_event] = ([*_existing_business, _business_handler] if isinstance(_existing_business, list) else [_existing_business, _business_handler] if _existing_business else _business_handler)
_project_update = doc_events["Project"].get("on_update")
doc_events["Project"]["on_update"] = ([_project_update] if isinstance(_project_update, str) else (_project_update or [])) + ["client_akivision.utils.project_progress_events.after_project_update"]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {"*/10 * * * *": ["client_akivision.utils.project_business_progress.refresh_active_projects"]},
	# 每日自检：是否到达设置的评级周期（周/月/季），未到期立即返回。
	"daily": [
		"client_akivision.utils.inventory_impairment.scheduled_assess_items",
		"client_akivision.utils.supplier_rating.scheduled_update_supplier_ratings",
		"client_akivision.utils.project_progress.scheduled_recalculate_project_progress",
		"client_akivision.utils.purchase_order_payment_flow.backfill_purchase_order_flow_status",
	],
}

# scheduler_events = {
# 	"all": [
# 		"client_akivision.tasks.all"
# 	],
# 	"daily": [
# 		"client_akivision.tasks.daily"
# 	],
# 	"hourly": [
# 		"client_akivision.tasks.hourly"
# 	],
# 	"weekly": [
# 		"client_akivision.tasks.weekly"
# 	],
# 	"monthly": [
# 		"client_akivision.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "client_akivision.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "client_akivision.custom.task.CustomTaskMixin"
# }
extend_doctype_class = {
	"BOM": ["client_akivision.utils.bom.AkivisionBOMMixin"],
}

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"erpnext.stock.get_item_details.get_item_details": "client_akivision.api.sales_product_item_details.get_item_details",
	"erpnext.stock.get_item_details.get_valuation_rate": "client_akivision.api.sales_product_item_details.get_valuation_rate",
	"erpnext.stock.doctype.item.item.get_item_details": "client_akivision.api.sales_product_item_details.get_item_master_details",
	"erpnext.stock.utils.get_stock_balance": "client_akivision.api.sales_product_item_details.get_stock_balance",
	"erpnext.stock.get_item_details.get_bin_details": "client_akivision.api.sales_product_item_details.get_bin_details",
	"erpnext.stock.get_item_details.get_projected_qty": "client_akivision.api.sales_product_item_details.get_projected_qty",
	"erpnext.stock.get_item_details.apply_price_list": "client_akivision.api.sales_product_item_details.apply_price_list",
}
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "client_akivision.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Material Request": "client_akivision.utils.purchase_comparison.get_material_request_dashboard",
	"Purchase Comparison": "client_akivision.utils.purchase_comparison.get_purchase_comparison_dashboard",
	"Work Order": "client_akivision.utils.work_order_dashboard.get_work_order_dashboard",
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["client_akivision.utils.before_request"]
# after_request = ["client_akivision.utils.after_request"]

# Job Events
# ----------
# before_job = ["client_akivision.utils.before_job"]
# after_job = ["client_akivision.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"client_akivision.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
