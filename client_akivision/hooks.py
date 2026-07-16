app_name = "client_akivision"
app_title = "Client Akivision"
app_publisher = "yuewei"
app_description = "akivision"
app_email = "akivision@example.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

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
	"/assets/client_akivision/js/stock_settings_naming.js",
	"/assets/client_akivision/js/desktop_icon_logo.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/client_akivision/css/client_akivision.css"
# web_include_js = "/assets/client_akivision/js/client_akivision.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "client_akivision/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Supplier Scorecard": "public/js/supplier_scorecard.js",
	"Stock Entry": "public/js/stock_entry.js",
}
doctype_list_js = {
	"Supplier": "public/js/supplier_list.js",
	"Customer": "public/js/customer_list.js",
	"Purchase Receipt": "public/js/purchase_receipt_list.js",
	"Finished Goods Status": "public/js/finished_goods_status_list.js",
}

# Keep the Selling workspace configuration in the database, but limit what is
# returned in the sidebar payload sent to desk users.
boot_session = "client_akivision.utils.workspace_sidebar.hide_selling_pos_and_non_delivery_reports"
after_migrate = [
	"client_akivision.utils.operations_management.sync_operations_management_desktop_icon",
	"client_akivision.utils.selling_sidebar.sync_selling_sidebar_entries",
]
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

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Stock Entry": {
		"on_submit": [
			"client_akivision.utils.sample_loan.on_stock_entry_submit",
			"client_akivision.utils.sample_loan.on_stock_entry_submit_for_fgs",
		],
		"on_cancel": [
			"client_akivision.utils.sample_loan.on_stock_entry_cancel",
		],
	},
	"Purchase Receipt": {
		"on_submit": "client_akivision.utils.sample_loan.on_purchase_receipt_submit",
		"validate": "client_akivision.utils.purchase_receipt.set_purchase_order_from_items",
	},
	"Supplier Scorecard": {
		"on_update": "client_akivision.utils.supplier_scorecard.update_supplier_rating",
	},
	"Supplier Scorecard Period": {
		"on_submit": "client_akivision.utils.supplier_scorecard.refresh_supplier_rating_from_period",
		"on_cancel": "client_akivision.utils.supplier_scorecard.refresh_supplier_rating_from_period",
	},
	"BOM": {
		"validate": "client_akivision.utils.engineering_drawing.validate_bom_drawing",
	},
	"Material Request": {
		"validate": "client_akivision.utils.engineering_drawing.set_material_request_drawing_reference",
	},
	"Work Order": {
		"validate": "client_akivision.utils.engineering_drawing.set_work_order_drawing_reference",
	},
	"Supplier": {
		"after_insert": "client_akivision.utils.supplier_scorecard.create_supplier_scorecard",
	},
}

# Scheduled Tasks
# ---------------

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

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "client_akivision.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "client_akivision.task.get_dashboard_data"
# }

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
