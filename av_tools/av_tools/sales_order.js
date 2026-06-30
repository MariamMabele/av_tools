// Sales Order shortcut bindings (moved from csf_tz)

frappe.require([
	"/assets/av_tools/js/shortcuts.js",
]);

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+q",
	action: () => {
		ctrlQ("Sales Order Item");
	},
	page: this.page,
	description: __("Select Item Warehouse"),
	ignore_inputs: true,
});

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+i",
	action: () => {
		ctrlI("Sales Order Item");
	},
	page: this.page,
	description: __("Select Customer Item Price"),
	ignore_inputs: true,
});

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+u",
	action: () => {
		ctrlU("Sales Order Item");
	},
	page: this.page,
	description: __("Select Item Price"),
	ignore_inputs: true,
});
