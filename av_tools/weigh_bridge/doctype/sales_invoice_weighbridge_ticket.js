const TARGET_DOCTYPE = "Sales Invoice";
const PARTY_FIELD = "customer";

const set_weighbridge_query = (frm) => {
  if (!frm.fields_dict.weighbridge_ticket) {
    return;
  }

  const query = () => ({
    filters: {
      target_document_type: ["in", ["", null, TARGET_DOCTYPE]],
      target_document_reference: ["in", ["", null]],
      document_type: ["!=", TARGET_DOCTYPE],
      docstatus: 1,
    },
  });

  frm.set_query("weighbridge_ticket", query);
  frm.fields_dict.weighbridge_ticket.get_query = query;
};

const set_fields_if_present = (frm, values) => {
  Object.entries(values || {}).forEach(([fieldname, value]) => {
    if (value === undefined || !frm.fields_dict[fieldname]) {
      return;
    }
    frm.set_value(fieldname, value);
  });
};

const add_create_ticket_button = (frm) => {
  if (frm.doc.docstatus !== 1) {
    return;
  }

  frm.add_custom_button(
    __("Weighbridge Ticket"),
    () => {
      frappe.call({
        method: "av_tools.weigh_bridge.api.create_weighbridge_ticket",
        args: {
          source_name: frm.doc.name,
          source_doctype: frm.doctype
        },
        freeze: true,
        freeze_message: __("Creating Weighbridge Ticket..."),
        callback: (r) => {
          if (r.message) {
            const url = frappe.urllib.get_full_url(`/app/weighbridge-ticket/${r.message}`);
            window.open(url, '_blank');
          }
        }
      });
    },
    __("Create")
  );
};

const apply_ticket_items = (frm, ticket) => {
  const items = ticket.items || [];
  if (!items.length) {
    frappe.msgprint(__("Selected Weighbridge Ticket has no items."));
    return;
  }

  const byItemCode = {};
  items.forEach((row) => {
    const itemCode = (row.item_code || "").trim();
    if (!itemCode) return;
    byItemCode[itemCode] = byItemCode[itemCode] || [];
    byItemCode[itemCode].push(row);
  });

  const keep = [];
  (frm.doc.items || []).forEach((docRow) => {
    const itemCode = (docRow.item_code || "").trim();
    const matches = itemCode ? byItemCode[itemCode] : null;
    if (!matches || !matches.length) {
      return;
    }

    const ticketRow = matches.shift();

    if (ticketRow.qty != null) docRow.qty = ticketRow.qty;
    // Keep mapped UOM to satisfy previous-doc validation (SO/DN rows).

    if (ticketRow.sales_order && docRow.sales_order !== undefined) {
      docRow.sales_order = ticketRow.sales_order;
    }
    if (ticketRow.so_detail && docRow.so_detail !== undefined) {
      docRow.so_detail = ticketRow.so_detail;
    }

    keep.push(docRow);
  });

  Object.values(byItemCode).forEach((pending) => {
    (pending || []).forEach((row) => {
      const child = frm.add_child("items");
      child.item_code = row.item_code;
      if (row.item_name) child.item_name = row.item_name;
      if (row.qty != null) child.qty = row.qty;
      // Don't force UOM on target docs; keep system defaults / mapped values.
      if (row.sales_order) child.sales_order = row.sales_order;
      if (row.so_detail) child.so_detail = row.so_detail;
      keep.push(child);
    });
  });

  frm.doc.items = keep;
  frm.refresh_field("items");
};

const apply_ticket_fields = (frm, ticket) => {
  const values = {
    company: ticket.company || undefined,
    posting_date: ticket.posting_date || undefined,
    transaction_date: ticket.posting_date || undefined,
    due_date: ticket.posting_date || undefined,
    set_posting_time: 1,
    posting_time: ticket.posting_time || undefined,
  };

  if (PARTY_FIELD === "customer") {
    values.customer = ticket.customer || undefined;
  } else {
    values.supplier = ticket.supplier || undefined;
  }

  set_fields_if_present(frm, values);
};

const handle_ticket_change = (frm, options = {}) => {
  if (!frm.doc.weighbridge_ticket) {
    return;
  }

  const { apply_values = true } = options;
  const documentName = frm.is_new() ? "" : frm.doc.name || "";

  frappe.call({
    method: "av_tools.weigh_bridge.api.get_ticket_items",
    args: {
      ticket: frm.doc.weighbridge_ticket,
      doctype: frm.doctype,
      document_name: documentName,
    },
    callback: (r) => {
      if (!r.message) {
        frappe.msgprint(__("Unable to load Weighbridge Ticket."));
        return;
      }

      if (!apply_values) {
        return;
      }

      apply_ticket_fields(frm, r.message);
      apply_ticket_items(frm, { items: r.message.items || [] });
    },
  });
};

frappe.ui.form.on(TARGET_DOCTYPE, {
  onload(frm) {
    set_weighbridge_query(frm);

    if (frm.doc.weighbridge_ticket && (!frm.doc.items || !frm.doc.items.length)) {
      handle_ticket_change(frm);
    }
  },
  refresh(frm) {
    set_weighbridge_query(frm);
    add_create_ticket_button(frm);
  },
  weighbridge_ticket(frm) {
    handle_ticket_change(frm);
  },
  after_save(frm) {
    if (frm.doc.weighbridge_ticket) {
      handle_ticket_change(frm, { apply_values: false });
    }
  },
});
