app_name = "av_tools"
app_title = "Av Tools"
app_publisher = "Aakvatech"
app_description = "Av Tools"
app_email = "info@aakvatech.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "av_tools",
# 		"logo": "/assets/av_tools/logo.png",
# 		"title": "Av Tools",
# 		"route": "/av_tools",
# 		"has_permission": "av_tools.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/av_tools/css/av_tools.css"
app_include_js = [
	"/assets/av_tools/js/financial_statements_override.js",
	"/assets/av_tools/js/ai_assist.js",
]
app_include_css = "/assets/av_tools/css/theme.css"

# include js, css files in header of web template
web_include_css = "/assets/av_tools/css/theme.css"
# web_include_js = "/assets/av_tools/js/av_tools.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "av_tools/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {
	"Sales Invoice": [
		"weigh_bridge/doctype/sales_invoice_weighbridge_ticket.js",
		"authotp/api/sales_invoice.js",
		"av_tools/sales_invoice.js",
		"av_tools/item_remaining_qty.js",
	],
	"Delivery Note": [
		"weigh_bridge/doctype/delivery_note_weighbridge_ticket.js",
		"av_tools/delivery_note.js",
	],
	"Sales Order": [
		"weigh_bridge/doctype/sales_order_weighbridge_ticket.js",
		"av_tools/sales_order.js",
	],
	"Purchase Order": [
		"weigh_bridge/doctype/purchase_order_weighbridge_ticket.js",
		"av_tools/purchase_order.js",
	],
	"Stock Entry": "av_tools/stock_entry.js",
	"Purchase Invoice": "weigh_bridge/doctype/purchase_invoice_weighbridge_ticket.js",
	"Purchase Receipt": "weigh_bridge/doctype/purchase_receipt_weighbridge_ticket.js",
	"Material Request": "av_tools/material_request.js",
	"Customer": "authotp/api/customer.js",
	"Account": "av_tools/account.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "av_tools/public/icons.svg"

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

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "av_tools.utils.jinja_methods",
# 	"filters": "av_tools.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "av_tools.install.before_install"
before_install = "av_tools.install.before_install"
after_install = [
	"av_tools.weigh_bridge.custom_fields.setup_custom_fields",
	"av_tools.patches.custom_fields.auth_otp_custom_fields.execute",
	"av_tools.utils.create_custom_fields.execute",
	"av_tools.utils.create_property_setter.execute",
]
after_migrate = [
	"av_tools.weigh_bridge.custom_fields.setup_custom_fields",
	"av_tools.utils.create_custom_fields.execute",
	"av_tools.utils.create_property_setter.execute",
	"av_tools.patches.v1_0.migrate_ai_integration_site_data.execute",
	"av_tools.patches.v1_0.migrate_report_extension_site_data.execute",
]

# Uninstallation
# ------------

# before_uninstall = "av_tools.uninstall.before_uninstall"
# after_uninstall = "av_tools.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "av_tools.utils.before_app_install"
# after_app_install = "av_tools.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "av_tools.utils.before_app_uninstall"
# after_app_uninstall = "av_tools.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "av_tools.notifications.get_notification_config"

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

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }
doc_events = {
	"Sales Invoice": {
		"validate": [
			"av_tools.weigh_bridge.validation.validate_weighbridge_ticket",
			"av_tools.av_tools_hooks.trade_in.validate_trade_in_serial_no_and_batch",
			"av_tools.av_tools_hooks.trade_in.validate_trade_in_sales_percentage",
			"av_tools.av_tools_hooks.item_remaining_qty.validate_items_remaining_qty",
		],
		"before_submit": "av_tools.authotp.api.sales_invoice.before_submit",
		"on_submit": "av_tools.av_tools_hooks.trade_in.create_trade_in_stock_entry",
	},
	"Delivery Note": {"validate": "av_tools.weigh_bridge.validation.validate_weighbridge_ticket"},
	"Sales Order": {"validate": "av_tools.weigh_bridge.validation.validate_weighbridge_ticket"},
	"Purchase Order": {
		"validate": [
			"av_tools.weigh_bridge.validation.validate_weighbridge_ticket",
			"av_tools.av_tools_hooks.purchase_order.target_warehouse_based_price_list",
		]
	},
	"Purchase Invoice": {"validate": "av_tools.weigh_bridge.validation.validate_weighbridge_ticket"},
	"Purchase Receipt": {"validate": "av_tools.weigh_bridge.validation.validate_weighbridge_ticket"},
	"Custom DocPerm": {
		"validate": "av_tools.av_tools_hooks.custom_docperm.grant_dependant_access",
	},
	"Account": {
		"on_update": "av_tools.av_tools_hooks.account.create_indirect_expense_item",
		"after_insert": "av_tools.av_tools_hooks.account.create_indirect_expense_item",
	},
	"*": {
		"validate": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"onload": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_insert": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"after_insert": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_naming": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_change": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_update_after_submit": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_validate": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_save": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_update": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"before_submit": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"autoname": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_cancel": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_trash": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_submit": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_update_after_submit": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
		"on_change": ["av_tools.av_tools.doctype.visibility.visibility.run_visibility"],
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"0 */6 * * *": [
			"av_tools.av_tools.doctype.parking_bill.parking_bill.check_bills_all_vehicles",
		]
	},
	"daily": [
		"av_tools.av_tools.doctype.visibility.visibility.trigger_daily_alerts",
		"av_tools.compliance.doctype.license_register.license_register.update_license_statuses",
	],
}

# Testing
# -------

# before_tests = "av_tools.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"frappe.desk.search.search_link": "av_tools.av_tools_hooks.item_search.search_link",
	"frappe.desk.search.search_widget": "av_tools.av_tools_hooks.item_search.search_widget",
	"frappe.desk.query_report.get_script": "av_tools.av_tools_hooks.query_report.get_script",
	"erpnext.buying.doctype.purchase_order.purchase_order.update_status": "av_tools.av_tools_hooks.generic_erp_behavior_overrides.update_purchase_order_status",
	"erpnext.buying.doctype.purchase_order.purchase_order.close_or_unclose_purchase_orders": "av_tools.av_tools_hooks.generic_erp_behavior_overrides.close_or_unclose_purchase_orders",
	"erpnext.stock.doctype.material_request.material_request.update_status": "av_tools.av_tools_hooks.generic_erp_behavior_overrides.update_material_request_status",
	"erpnext.stock.get_item_details.get_item_details": "av_tools.av_tools_hooks.generic_erp_behavior_overrides.get_item_details",
}

# Override doctype class to intercept report execution
override_doctype_class = {"Report": "av_tools.av_tools_hooks.report_override.ReportOverride"}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "av_tools.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["av_tools.utils.before_request"]
# after_request = ["av_tools.utils.after_request"]

# Job Events
# ----------
# before_job = ["av_tools.utils.before_job"]
# after_job = ["av_tools.utils.after_job"]

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
# 	"av_tools.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
