frappe.require([
	"/assets/av_tools/js/po_shortcuts.js",
]);

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+i",
	action: () => {
		ctrlI("Purchase Order Item");
	},
	page: this.page,
	description: __("Select Customer Item Price"),
	ignore_inputs: true,
});

frappe.ui.keys.add_shortcut({
	shortcut: "ctrl+u",
	action: () => {
		ctrlU("Purchase Order Item");
	},
	page: this.page,
	description: __("Select Item Price"),
	ignore_inputs: true,
});

frappe.ui.form.on("Purchase Order Item", {
	item_code: async function (frm, cdt, cdn) {
		await set_dynamic_price_list_rate(frm, cdt, cdn);
	},
	warehouse: async function (frm, cdt, cdn) {
		await set_dynamic_price_list_rate(frm, cdt, cdn);
	},
});

async function set_dynamic_price_list_rate(frm, cdt, cdn) {
	const item = locals[cdt][cdn];
	const price_list_rate = await get_dynamic_price_list_rate(
		frm,
		item.item_code,
		item.warehouse,
	);

	if (price_list_rate == null) {
		return;
	}

	frappe.model.set_value(cdt, cdn, "price_list_rate", price_list_rate);
	frappe.model.set_value(cdt, cdn, "rate", price_list_rate);
	frappe.model.set_value(cdt, cdn, "amount", price_list_rate * (item.qty || 0));
}

async function get_dynamic_price_list_rate(frm, item_code, warehouse) {
	const enabled = await frappe.db.get_single_value(
		"AV Tools Settings",
		"target_warehouse_based_price_list",
	);

	if (!enabled) {
		return null;
	}

	if (!item_code || !warehouse || !frm.doc.supplier) {
		frappe.throw("Item Code, Warehouse and Supplier are required");
	}

	const price_list = await frappe.db.get_value(
		"Dynamic Price List Assignment",
		{ supplier: frm.doc.supplier, warehouse: warehouse },
		"price_list",
	);

	if (!price_list.message.price_list) {
		frappe.throw(
			"Price List not found. Please create one in Dynamic Price List Assignment for "
			+ frm.doc.supplier + " and " + warehouse,
		);
	}

	const price_list_rate = await frappe.db.get_value(
		"Item Price",
		{ item_code: item_code, price_list: price_list.message.price_list },
		"price_list_rate",
	);

	if (!price_list_rate.message.price_list_rate) {
		frappe.throw("Price List not found for Item " + item_code + ". Please create one.");
	}

	return price_list_rate.message.price_list_rate;
}
