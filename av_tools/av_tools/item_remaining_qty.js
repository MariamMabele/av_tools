// Copyright (c) 2026, Aakvatech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Sales Invoice Item", {
  item_code: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_qty(frm, cdt, cdn);
  },
  qty: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_qty(frm, cdt, cdn);
  },
  stock_qty: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_stock_qty(frm, cdt, cdn);
  },
  uom: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_qty(frm, cdt, cdn);
  },
  allow_over_sell: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_stock_qty(frm, cdt, cdn);
  },
  conversion_factor: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_stock_qty(frm, cdt, cdn);
  },
  warehouse: function (frm, cdt, cdn) {
    av_tools_validate_item_remaining_stock_qty(frm, cdt, cdn);
  },
});

var av_tools_validate_item_remaining_qty = function (frm, cdt, cdn) {
  const item_row = locals[cdt][cdn];
  if (item_row.item_code == null) {
    return;
  }
  if (item_row.allow_over_sell == 1) {
    return;
  }
  const conversion_factor = av_tools_get_conversion_factor(
    item_row,
    item_row.item_code,
    item_row.uom
  );
  frappe.call({
    method:
      "av_tools.av_tools_hooks.item_remaining_qty.validate_item_remaining_qty",
    args: {
      item_code: item_row.item_code,
      company: frm.doc.company,
      warehouse: item_row.warehouse,
      stock_qty: item_row.qty * conversion_factor,
      so_detail: item_row.so_detail,
    },
    async: false,
  });
};

var av_tools_validate_item_remaining_stock_qty = function (frm, cdt, cdn) {
  const item_row = locals[cdt][cdn];
  if (item_row.item_code == null) {
    return;
  }
  if (item_row.allow_over_sell == 1) {
    return;
  }
  frappe.call({
    method:
      "av_tools.av_tools_hooks.item_remaining_qty.validate_item_remaining_qty",
    args: {
      item_code: item_row.item_code,
      company: frm.doc.company,
      warehouse: item_row.warehouse,
      stock_qty: item_row.stock_qty,
    },
    async: false,
  });
};

var av_tools_get_conversion_factor = function (item_row, item_code, uom) {
  if (item_code && uom) {
    let conversion_factor = 0;
    frappe.call({
      method: "erpnext.stock.get_item_details.get_conversion_factor",
      child: item_row,
      args: {
        item_code: item_code,
        uom: uom,
      },
      async: false,
      callback: function (r) {
        if (!r.exc) {
          conversion_factor = r.message.conversion_factor;
        }
      },
    });
    return conversion_factor;
  }
};
