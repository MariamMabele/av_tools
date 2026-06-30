import frappe

# Trade In custom fields previously created by csf_tz. av_tools now owns them
# and (re)creates them via av_tools.utils.create_custom_fields. This patch just
# re-homes any pre-existing copies to the "Trade In" module of av_tools.
CUSTOM_FIELDS = (
	"Sales Invoice Item-custom_uom",
	"Sales Invoice Item-custom_trade_in_details",
	"Sales Invoice Item-custom_trade_in_item",
	"Sales Invoice Item-custom_trade_in_qty",
	"Sales Invoice Item-custom_trade_in_uom",
	"Sales Invoice Item-custom_trade_in_column",
	"Sales Invoice Item-custom_trade_in_incoming_rate",
	"Sales Invoice Item-custom_total_trade_in_value",
	"Sales Invoice Item-custom_trade_in_batch_no",
	"Sales Invoice Item-custom_trade_in_serial_no",
	"Sales Invoice-custom_is_trade_in",
	"Stock Entry-custom_sales_invoice",
	"Company-custom_trade_in_settings",
	"Company-custom_trade_in_sales_percentage",
	"Company-custom_trade_in_control_account",
)


def execute():
	for cf_name in CUSTOM_FIELDS:
		if frappe.db.exists("Custom Field", cf_name):
			frappe.db.set_value("Custom Field", cf_name, "module", "Trade In")

	# The "Trade In" Module Def used to belong to csf_tz; hand it to av_tools.
	if frappe.db.exists("Module Def", "Trade In"):
		frappe.db.set_value("Module Def", "Trade In", "app_name", "av_tools")
