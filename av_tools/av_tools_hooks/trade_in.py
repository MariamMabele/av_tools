import frappe
from frappe import _


def _is_feature_enabled():
	return bool(frappe.db.get_single_value("AV Tools Settings", "enable_trade_in"))


def trade_in_flag_check(func):
	def wrapper(doc, method=None, *args, **kwargs):
		if not _is_feature_enabled():
			return  # Skip if the Trade In feature is disabled
		if not getattr(doc, "custom_is_trade_in", False):
			return  # Skip validation if trade-in is not applicable
		return func(doc, method, *args, **kwargs)  # Call the original function if validation is needed

	return wrapper


@trade_in_flag_check
def validate_trade_in_serial_no_and_batch(doc, method):
	error_messages = []
	for row in doc.items:
		if row.item_code == "Trade In" and row.custom_trade_in_item:
			has_batch_no = frappe.db.get_value("Item", row.custom_trade_in_item, "has_batch_no")
			if has_batch_no and not row.custom_trade_in_batch_no:
				error_messages.append(
					_("Batch No. is mandatory for Item {0} in row {1}.").format(
						row.custom_trade_in_item, row.idx
					)
				)

			has_serial_no = frappe.db.get_value("Item", row.custom_trade_in_item, "has_serial_no")
			if has_serial_no:
				if not row.custom_trade_in_serial_no:
					error_messages.append(
						_("Serial Numbers are mandatory for Item {0} in row {1}.").format(
							row.custom_trade_in_item, row.idx
						)
					)
				else:
					serial_numbers = row.custom_trade_in_serial_no.split("\n")
					if len(serial_numbers) != row.custom_trade_in_qty:
						error_messages.append(
							_(
								"Serial Numbers count ({0}) does not match the Trade-In Quantity"
								" ({1}) for Item {2} in row {3}."
							).format(
								len(serial_numbers),
								row.custom_trade_in_qty,
								row.custom_trade_in_item,
								row.idx,
							)
						)
	if error_messages:
		frappe.throw(
			title=_("Validation Errors"),
			msg="<br>".join(error_messages),
		)


@trade_in_flag_check
def validate_trade_in_sales_percentage(doc, method):
	# Calculate the total trade-in value from the child table where item_code = "Trade In"
	total_trade_in_value = sum(
		row.custom_total_trade_in_value for row in doc.items if row.item_code == "Trade In"
	)

	# If there are no trade-in items, skip validation
	if total_trade_in_value == 0:
		return  # No validation needed

	# Calculate the total for items in the child table where item_code != "Trade In"
	non_trade_in_total = sum(row.amount for row in doc.items if row.item_code != "Trade In")

	# Fetch allowed percentage from the Company doctype
	trade_in_percentage = frappe.db.get_value("Company", doc.company, "custom_trade_in_sales_percentage") or 0

	# Calculate the allowed trade-in value based on the percentage of non-trade-in total
	allowed_trade_in_value = (trade_in_percentage / 100) * non_trade_in_total

	# Validate total trade-in value
	if total_trade_in_value > allowed_trade_in_value:
		# Throw error if child table total exceeds the allowed limit. The HTML scaffold is
		# markup, not translatable copy, so it is intentionally not wrapped in _().
		total_value_display = frappe.format_value(total_trade_in_value)
		allowed_value_display = frappe.format_value(allowed_trade_in_value)
		frappe.throw(
			title=_("Trade-In Value Validation Error"),
			msg=f"""
        <h4>Trade-In Value Validation Error</h4>
        <p>The Total Trade-In Value exceeds the allowed limit. Please review the details below:</p>
        <table style="border-collapse: collapse; width: 100%; text-align: left; border: 1px solid #ddd;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Description</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Value</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Total Trade-In Value</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{total_value_display}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Allowed Trade-In Percentage</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{trade_in_percentage}%</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Maximum Allowed Trade-In Value</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">{allowed_value_display}</td>
                </tr>
            </tbody>
        </table>
        <p>Please adjust the trade-in value or reduce the quantity of trade-in items.</p>
    """,
		)


@trade_in_flag_check
def create_trade_in_stock_entry(doc, method):
	# Initialize an empty list to store items
	items_list = []

	# Fetch Company's Trade In control account
	company_details = frappe.db.get_value(
		"Company",
		doc.company,
		["custom_trade_in_control_account"],
		as_dict=True,
	)
	if not company_details:
		frappe.throw(
			_("Company details not found for {0}. Please check the Company configuration.").format(
				doc.company
			)
		)
		return

	trade_in_control_account = company_details.get("custom_trade_in_control_account")

	if not trade_in_control_account:
		frappe.throw(
			_(
				"Trade-In Control Account not configured for {0}. "
				"Please set it in the <a href='/app/company/{0}'>Company settings</a>."
			).format(doc.company)
		)
		return

	# Iterate through the items in the document
	for item in doc.items:
		if item.get("custom_trade_in_item") and item.get("custom_trade_in_qty"):
			# Check if custom_trade_in_batch_no exists
			custom_batch_no = item.get("custom_trade_in_batch_no")

			if custom_batch_no:
				# Check if a Batch with this ID already exists
				batch_exists = frappe.db.exists("Batch", {"batch_id": custom_batch_no})
				if not batch_exists:
					try:
						# Create a new batch with the given custom_trade_in_batch_no
						batch_doc = frappe.new_doc("Batch")
						batch_doc.item = item.get("custom_trade_in_item")
						batch_doc.batch_id = custom_batch_no  # Use the provided custom batch number
						batch_doc.save()
					except Exception as e:
						frappe.throw(_("Error creating Batch: {0}").format(str(e)))

			# Append each item's details to the items_list
			items_list.append(
				{
					"item_code": item.get("custom_trade_in_item"),
					"qty": item.get("custom_trade_in_qty"),
					"uom": item.get("uom") or "Nos",  # Default to "Nos" if UOM is not provided
					"basic_rate": item.get("custom_trade_in_incoming_rate"),
					"batch_no": custom_batch_no,  # Use the custom batch number here
					"serial_no": item.get("custom_trade_in_serial_no"),  # Custom serial number value
					"expense_account": trade_in_control_account,
					"t_warehouse": item.get(
						"warehouse"
					),  # Use the warehouse from the Sales Invoice child table
					"use_serial_batch_fields": 1,
				}
			)

	# Create a single stock entry if there are items to add
	if items_list:
		try:
			stock_entry = frappe.get_doc(
				{
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"items": items_list,  # Use the populated list here
					"custom_sales_invoice": doc.name,  # Link to the parent Sales Invoice
				}
			)

			# Insert and submit the Stock Entry
			stock_entry.insert()
			stock_entry.submit()

			# Notify the user
			frappe.msgprint(
				_("Stock Entry {0} created successfully!").format(
					f"<a href='/app/stock-entry/{stock_entry.name}' target='_blank'>{stock_entry.name}</a>"
				)
			)
		except Exception as e:
			frappe.throw(_("Error during Stock Entry creation: {0}").format(str(e)))
	else:
		frappe.msgprint(_("No valid items found for stock entry."))
