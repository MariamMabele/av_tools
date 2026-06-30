# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from av_tools.trade_in.utils import (
	add_trade_in_control_account,
	add_trade_in_item,
	add_trade_in_module,
	delete_trade_in_item_and_account,
	set_negative_rates_for_items,
)


class AVToolsSettings(Document):
	def on_update(self):
		self.manage_trade_in_functionality()

	def manage_trade_in_functionality(self):
		if not self.has_value_changed("enable_trade_in"):
			return

		# Check if the feature is being enabled
		if self.enable_trade_in:
			try:
				add_trade_in_module()  # Add Trade In module
				add_trade_in_item()  # Create Trade In item
				add_trade_in_control_account()  # Create Control Account
				set_negative_rates_for_items()  # Allow negative rates for items
				frappe.msgprint(_("Trade In feature has been successfully enabled."))
			except Exception as e:
				# Log the error and notify the user
				frappe.log_error(f"Error enabling Trade In feature: {e!s}")
				frappe.msgprint(_("Failed to enable Trade In feature: {0}").format(str(e)))
		else:
			# If the feature is being disabled, delete the associated item and account
			try:
				delete_trade_in_item_and_account()  # Delete Trade In item and Control Account
				frappe.msgprint(_("Trade In feature has been successfully disabled."))
			except Exception as e:
				# Log the error and notify the user
				frappe.log_error(f"Error disabling Trade In feature: {e!s}")
				frappe.msgprint(_("Failed to disable Trade In feature: {0}").format(str(e)))
