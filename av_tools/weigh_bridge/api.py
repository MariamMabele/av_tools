import frappe
from frappe.utils import flt


ALLOWED_REFERENCE_DOCTYPES = {
    "Sales Invoice",
    "Delivery Note",
    "Sales Order",
    "Purchase Order",
    "Purchase Invoice",
    "Purchase Receipt",
}

ALLOWED_TARGETS_BY_SOURCE = {
    "Sales Order": {"Sales Invoice"},
    "Delivery Note": {"Sales Invoice"},
    "Purchase Order": {"Purchase Invoice"},
    "Purchase Receipt": {"Purchase Invoice"},
}


def _get_settings():
    settings = frappe.get_single("Weighbridge Settings")
    if not settings.enabled:
        frappe.throw("Weighbridge Settings is disabled.")
    if not settings.read_weight_url:
        frappe.throw("Read Weight URL is required in Weighbridge Settings.")
    return settings


@frappe.whitelist()
def get_uom_conversion_factor(from_uom, to_uom):
    """Return multiplier to convert qty in from_uom -> to_uom.

    Uses ERPNext UOM Conversion Factor rules (direct, inverse, intermediate).
    """
    from_uom = (from_uom or "").strip()
    to_uom = (to_uom or "").strip()
    if not from_uom or not to_uom:
        frappe.throw("From UOM and To UOM are required.")
    if from_uom == to_uom:
        return {"conversion_factor": 1.0}

    from erpnext.stock.doctype.item.item import get_uom_conv_factor

    return {"conversion_factor": flt(get_uom_conv_factor(from_uom, to_uom))}


def _apply_ticket_items_to_target(target_doc, ticket_doc):
    """Mutate target_doc.items to match ticket items (item_code + qty + uom),
    while preserving other mapped fields on existing rows.
    """

    ticket_items = ticket_doc.get("items") or []
    if not ticket_items:
        frappe.throw("Selected Weighbridge Ticket has no items.")

    ticket_by_item_code = {}
    for row in ticket_items:
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            continue
        ticket_by_item_code.setdefault(item_code, []).append(row)

    kept_rows = []
    for row in (target_doc.get("items") or []):
        item_code = (row.get("item_code") or "").strip()
        matches = ticket_by_item_code.get(item_code) if item_code else None
        if not matches:
            continue

        ticket_row = matches.pop(0)
        if ticket_row.get("qty_in_kg") is not None:
            # Convert from kg to the row's existing uom (keep uom to satisfy previous-doc validation).
            if row.get("uom") and row.uom.lower() != "kg":
                from erpnext.stock.doctype.item.item import get_uom_conv_factor

                row.qty = flt(ticket_row.get("qty_in_kg")) * flt(get_uom_conv_factor("Kg", row.uom))
            else:
                row.qty = flt(ticket_row.get("qty_in_kg"))
        elif ticket_row.get("qty") is not None:
            row.qty = flt(ticket_row.get("qty"))

        if ticket_row.get("description"):
            row.description = ticket_row.get("description")

        # Optional sales order link fields (present on some sales doctypes).
        if ticket_row.get("sales_order") and hasattr(row, "sales_order"):
            row.sales_order = ticket_row.get("sales_order")
        if ticket_row.get("so_detail") and hasattr(row, "so_detail"):
            row.so_detail = ticket_row.get("so_detail")

        kept_rows.append(row)

    # Add remaining ticket items that didn't exist on mapped target.
    for pending_rows in ticket_by_item_code.values():
        for ticket_row in pending_rows or []:
            child = target_doc.append("items", {})
            child.item_code = ticket_row.get("item_code")
            if ticket_row.get("item_name"):
                child.item_name = ticket_row.get("item_name")
            if ticket_row.get("description"):
                child.description = ticket_row.get("description")
            # For non-mapped adds (direct from ticket), exactly copy the ticket's qty and uom
            if ticket_row.get("uom"):
                child.uom = ticket_row.get("uom")
                
            if ticket_row.get("qty") is not None:
                child.qty = flt(ticket_row.get("qty"))
            elif ticket_row.get("qty_in_kg") is not None:
                child.qty = flt(ticket_row.get("qty_in_kg"))
            if ticket_row.get("sales_order") and hasattr(child, "sales_order"):
                child.sales_order = ticket_row.get("sales_order")
            if ticket_row.get("so_detail") and hasattr(child, "so_detail"):
                child.so_detail = ticket_row.get("so_detail")

            from erpnext.stock.get_item_details import get_item_details
            
            args = frappe._dict({
                "item_code": child.item_code,
                "company": target_doc.company,
                "customer": target_doc.get("customer"),
                "supplier": target_doc.get("supplier"),
                "doctype": target_doc.doctype,
                "name": target_doc.name,
                "qty": child.qty,
                "uom": child.uom,
                "price_list": target_doc.get("selling_price_list") or target_doc.get("buying_price_list"),
                "currency": target_doc.get("currency")
            })
            
            details = get_item_details(args, target_doc)
            for k, v in details.items():
                if child.meta.has_field(k) and not child.get(k):
                    child.set(k, v)

            kept_rows.append(child)

    target_doc.set("items", kept_rows)


@frappe.whitelist()
def make_target_from_ticket(source_name):
    """Create a mapped target document from a submitted Weighbridge Ticket.

    Uses standard ERPNext mapper methods to pull all defaults, then overrides only
    ticket-controlled fields (items qty/uom + links), preserving everything else.
    """

    args = getattr(frappe.flags, "args", None) or {}
    target_doctype = (args.get("target_doctype") or "").strip()
    if not target_doctype:
        frappe.throw("Target Doctype is required.")

    ticket = frappe.get_doc("Weighbridge Ticket", source_name)
    if ticket.docstatus != 1:
        frappe.throw("Weighbridge Ticket must be submitted.")

    source_type = ticket.document_type
    source_name = ticket.document_reference

    target = None
    if source_type and source_name:
        if source_type == "Sales Order" and target_doctype == "Sales Invoice":
            from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
            target = make_sales_invoice(source_name)
        elif source_type == "Delivery Note" and target_doctype == "Sales Invoice":
            from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
            target = make_sales_invoice(source_name)
        elif source_type == "Purchase Order" and target_doctype == "Purchase Invoice":
            from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
            target = make_purchase_invoice(source_name)
        elif source_type == "Purchase Receipt" and target_doctype == "Purchase Invoice":
            from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
            target = make_purchase_invoice(source_name)
        else:
            frappe.throw(f"Unsupported mapping: {source_type} -> {target_doctype}")
    else:
        # Create directly from Weighbridge Ticket without a source document
        target = frappe.new_doc(target_doctype)
        if ticket.company and target.meta.has_field("company"):
            target.company = ticket.company
        if ticket.customer and target.meta.has_field("customer"):
            target.customer = ticket.customer
        if ticket.supplier and target.meta.has_field("supplier"):
            target.supplier = ticket.supplier

    # Link ticket so existing validation + UI continue to work.
    if target.meta.has_field("weighbridge_ticket"):
        target.weighbridge_ticket = ticket.name

    # Prefer ticket posting date/time when target supports them.
    if ticket.get("posting_date") and target.meta.has_field("posting_date"):
        target.posting_date = ticket.posting_date
    if ticket.get("posting_time") and target.meta.has_field("posting_time"):
        target.posting_time = ticket.posting_time
    if target.meta.has_field("set_posting_time"):
        target.set_posting_time = 1

    _apply_ticket_items_to_target(target, ticket)

    # Re-apply document defaults after qty changes.
    target.flags.ignore_permissions = True
    target.run_method("set_missing_values")
    
    if target.doctype == "Sales Invoice" and target.get("customer") and not target.get("debit_to"):
        from erpnext.accounts.party import get_party_account
        target.debit_to = get_party_account("Customer", target.customer, target.company)
    
    if target.doctype == "Purchase Invoice" and target.get("supplier") and not target.get("credit_to"):
        from erpnext.accounts.party import get_party_account
        target.credit_to = get_party_account("Supplier", target.supplier, target.company)

    if target.doctype == "Sales Invoice":
        target.run_method("set_po_nos")
    target.run_method("calculate_taxes_and_totals")

    return target


@frappe.whitelist()
def read_weight(mode=None):
    settings = _get_settings()
    return {
        "read_weight_url": settings.read_weight_url,
        "mode": mode,
    }


@frappe.whitelist()
def get_gateway_payload():
    settings = _get_settings()
    return {
        "read_weight_url": settings.read_weight_url,
        "timeout_seconds": settings.timeout_seconds,
    }


@frappe.whitelist()
def get_reference_items(document_type=None, document_reference=None):
    if not document_type or not document_reference:
        frappe.throw("Document Type and Document Reference are required.")

    if document_type not in ALLOWED_REFERENCE_DOCTYPES:
        frappe.throw(f"Unsupported reference doctype: {document_type}")

    doc = frappe.get_doc(document_type, document_reference)
    doc.check_permission("read")

    if doc.meta.is_submittable and doc.docstatus == 2:
        frappe.throw(f"{document_type} {document_reference} is Cancelled.")

    items = []
    for row in (doc.get("items") or []):
        if not row.item_code:
            continue

        is_stock_item = frappe.db.get_value("Item", row.item_code, "is_stock_item")
        if not is_stock_item:
            continue

        items.append(
            {
                "item_code": row.item_code,
                "item_name": row.get("item_name"),
                "description": row.get("description"),
                "uom": row.get("uom"),
            }
        )

    return {
        "items": items,
        "company": doc.get("company"),
        "customer": doc.get("customer"),
        "supplier": doc.get("supplier"),
    }


@frappe.whitelist()
def get_ticket_items(ticket, doctype=None, document_name=None):
    if not ticket:
        frappe.throw("Weighbridge Ticket is required.")

    doc = frappe.get_doc("Weighbridge Ticket", ticket)
    if doc.docstatus != 1:
        frappe.throw("Weighbridge Ticket must be submitted.")

    is_source_request = (
        doctype
        and document_name
        and doc.document_type == doctype
        and doc.document_reference == document_name
    )

    if doctype and doc.document_type == doctype and not is_source_request:
        frappe.throw(
            f"Cannot use Weighbridge Ticket {doc.name} from {doc.document_type} as target {doctype}."
        )

    if (
        doctype
        and doc.target_document_type
        and doc.target_document_type != doctype
        and not is_source_request
    ):
        frappe.throw("Weighbridge Ticket target document type does not match.")
    if (
        document_name
        and doc.target_document_reference
        and doc.target_document_reference != document_name
        and not is_source_request
    ):
        frappe.throw("Weighbridge Ticket belongs to another document.")

    if (
        document_name
        and doctype
        and frappe.db.exists(doctype, document_name)
        and not is_source_request
    ):
        if doc.document_type:
            allowed_targets = ALLOWED_TARGETS_BY_SOURCE.get(doc.document_type, set())
            if doctype not in allowed_targets:
                frappe.throw(
                    f"Weighbridge source {doc.document_type} can only create: {', '.join(sorted(allowed_targets)) or 'None'}."
                )

        frappe.db.set_value(
            "Weighbridge Ticket",
            doc.name,
            {
                "target_document_type": doctype,
                "target_document_reference": document_name,
            },
            update_modified=True,
        )
        doc.target_document_type = doctype
        doc.target_document_reference = document_name

    so_name = None
    so_details_by_item_code = {}
    if doc.document_type == "Sales Order" and doc.document_reference:
        so_name = doc.document_reference
        so = frappe.get_doc("Sales Order", so_name)
        so.check_permission("read")
        for row in (so.get("items") or []):
            item_code = (row.get("item_code") or "").strip()
            so_detail = row.get("name")
            if not item_code or not so_detail:
                continue
            so_details_by_item_code.setdefault(item_code, []).append(so_detail)

    items = []
    for row in (doc.items or []):
        item_code = row.item_code
        if not item_code:
            continue
        item = {
            "item_code": item_code,
            "item_name": row.item_name,
            "description": row.description,
            "qty": row.qty,
            "uom": row.uom,
        }
        if so_name:
            item["sales_order"] = so_name
            details = so_details_by_item_code.get(item_code) or []
            if details:
                item["so_detail"] = details.pop(0)
        items.append(item)

    return {
        "items": items,
        "document_type": doc.document_type,
        "document_reference": doc.document_reference,
        "target_document_type": doc.target_document_type,
        "target_document_reference": doc.target_document_reference,
        "company": doc.company,
        "customer": doc.customer,
        "supplier": doc.supplier,
        "posting_date": doc.posting_date,
        "posting_time": doc.posting_time,
        "tare_weight": doc.tare_weight,
        "gross_weight": doc.gross_weight,
        "net_weight": doc.net_weight,
    }

@frappe.whitelist()
def create_weighbridge_ticket(source_name, source_doctype):
    if not source_name or not source_doctype:
        frappe.throw("Source Name and Doctype are required.")
        
    doc = frappe.get_doc(source_doctype, source_name)
    
    ticket = frappe.new_doc("Weighbridge Ticket")
    ticket.document_type = source_doctype
    ticket.document_reference = source_name
    ticket.company = doc.get("company")
    
    if source_doctype in ["Sales Order", "Sales Invoice", "Delivery Note"]:
        ticket.customer = doc.get("customer")
    else:
        ticket.supplier = doc.get("supplier")
        
    for row in (doc.get("items") or []):
        if not row.item_code:
            continue
            
        is_stock_item = frappe.db.get_value("Item", row.item_code, "is_stock_item")
        if not is_stock_item:
            continue
            
        child = ticket.append("items", {})
        child.item_code = row.item_code
        child.item_name = row.get("item_name")
        child.description = row.get("description")
        child.uom = row.get("uom")
        
    ticket.insert(ignore_permissions=True)
    return ticket.name

