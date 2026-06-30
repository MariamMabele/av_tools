// Trade In feature for Sales Invoice (moved from csf_tz)

frappe.require([
	"/assets/av_tools/js/shortcuts.js",
]);

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+q",
	action: () => {
		ctrlQ("Sales Invoice Item");
	},
	page: this.page,
	description: __("Select Item Warehouse"),
	ignore_inputs: true,
});

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+i",
	action: () => {
		ctrlI("Sales Invoice Item");
	},
	page: this.page,
	description: __("Select Customer Item Price"),
	ignore_inputs: true,
});

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+u",
	action: () => {
		ctrlU("Sales Invoice Item");
	},
	page: this.page,
	description: __("Select Item Price"),
	ignore_inputs: true,
});


frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		frm.trigger("set_trade_in_field_visibility");
	},
	onload: function (frm) {
		frm.trigger("set_trade_in_field_visibility");
	},

	set_trade_in_field_visibility: function (frm) {
		// Fetch the Enable Trade In setting from AV Tools Settings
		frappe.db
			.get_single_value("AV Tools Settings", "enable_trade_in")
			.then((enable_trade_in) => {
				// Show or hide the Custom Is Trade-In checkbox based on the setting
				frm.set_df_property("custom_is_trade_in", "hidden", !enable_trade_in);
			});
	},

	custom_is_trade_in: function (frm) {
		if (frm.doc.custom_is_trade_in) {
			frappe.db
				.get_value("Company", frm.doc.company, ["custom_trade_in_control_account"])
				.then((company_res) => {
					const trade_in_account = company_res?.message?.custom_trade_in_control_account;
					if (!trade_in_account)
						frappe.throw(
							__("Trade-In Control Account is not set in Company settings.")
						);

					if (!frm.doc.items.some((item) => item.item_code === "Trade In")) {
						frm.add_child("items", {
							item_code: "Trade In",
							item_name: "Trade In",
							income_account: trade_in_account,
							qty: 1,
							description: "Trade-In",
						});
						frm.refresh_field("items");
					}
				});
		} else {
			frappe.confirm(
				__('Are you sure you want to remove the "Trade In" item?'),
				() => {
					frm.doc.items = frm.doc.items.filter((item) => item.item_code !== "Trade In");
					frm.refresh_field("items");
				},
				() => frm.set_value("custom_is_trade_in", 1)
			);
		}
	},
});

frappe.ui.form.on("Sales Invoice Item", {
	custom_trade_in_qty: function (frm, cdt, cdn) {
		calculate_row_trade_in_value(frm, cdt, cdn);
	},
	custom_trade_in_item: function (frm, cdt, cdn) {
		// Reset serial numbers when item changes
		frappe.model.set_value(cdt, cdn, "custom_trade_in_serial_no", "");
	},
	custom_trade_in_incoming_rate: function (frm, cdt, cdn) {
		calculate_row_trade_in_value(frm, cdt, cdn);
	},
	item_code: function (frm, cdt, cdn) {
		set_trade_in_fields_readonly(frm);
	},
	form_render(frm, cdt, cdn) {
		// Get the current child table row document
		let row = locals[cdt][cdn];

		// Ensure row is defined before calling the function
		if (row) {
			// Check if the item_code is "Trade In"
			if (row.item_code === "Trade In") {
				// Use toggle_reqd to make the UOM field non-mandatory
				cur_frm.fields_dict.items.grid.toggle_reqd("uom", false);
			} else {
				// For non "Trade In" items, make the UOM field mandatory
				cur_frm.fields_dict.items.grid.toggle_reqd("uom", true);
			}
			set_trade_in_fields_readonly(frm, row);
		}
	},
});

// Calculate custom_total_trade_in_value for a specific row in the items child table
function calculate_row_trade_in_value(frm, cdt, cdn) {
	let row = locals[cdt][cdn];

	// Calculate custom_total_trade_in_value as custom_trade_in_qty * custom_trade_in_incoming_rate
	let total_value = (row.custom_trade_in_qty || 0) * (row.custom_trade_in_incoming_rate || 0);
	frappe.model.set_value(cdt, cdn, "custom_total_trade_in_value", total_value);

	// Set rate field as negative
	frappe.model.set_value(cdt, cdn, "rate", total_value * -1);
}

// Function to set trade-in fields read-only based on conditions
function set_trade_in_fields_readonly(frm, row) {
	if (!row || !row.item_code) {
		return; // Exit if row or item_code is not defined
	}

	const readonly_fields = [
		"item_name",
		"rate",
		"posa_special_discount",
		"posa_special_rate",
		"qty",
	];
	const is_trade_in = row.item_code === "Trade In" ? 1 : 0;

	readonly_fields.forEach((fieldname) => {
		frm.fields_dict.items.grid.update_docfield_property(
			fieldname,
			"read_only",
			is_trade_in,
			row.idx
		);
	});

	// Refresh the row to reflect the changes
	frm.refresh_field("items");
}
