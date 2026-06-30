# Copyright (c) 2026, Av Tools and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
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


def _build_qty_map(rows):
    qty_map = {}
    for row in (rows or []):
        item_code = (row.get("item_code") or "").strip()
        if not item_code:
            continue
        qty_map[item_code] = qty_map.get(item_code, 0) + flt(row.get("qty"))
    return qty_map


class WeighbridgeTicket(Document):
    def validate(self):
        self.validate_target_mapping()
        self.validate_items_against_reference()

    def on_submit(self):
        self.update_reference_document_quantities()
        self.update_vehicle_default_tare()

    def update_vehicle_default_tare(self):
        if not self.vehicle or not self.tare_weight:
            return

        current_default_tare = frappe.db.get_value("Vehicle", self.vehicle, "default_tare_weight")
        if not current_default_tare:
            frappe.db.set_value("Vehicle", self.vehicle, "default_tare_weight", self.tare_weight, update_modified=True)

    def on_cancel(self):
        self.clear_reference_document_link()

    def validate_target_mapping(self):
        source_type = self.document_type
        target_type = self.target_document_type

        if source_type and target_type and source_type == target_type:
            frappe.throw("Source and Target document types cannot be the same.")

        if source_type and target_type:
            allowed_targets = ALLOWED_TARGETS_BY_SOURCE.get(source_type, set())
            if target_type not in allowed_targets:
                frappe.throw(
                    f"Source {source_type} can only create: {', '.join(sorted(allowed_targets)) or 'None'}."
                )

    def validate_items_against_reference(self):
        # Reference is optional. Only validate against source document when provided.
        if not self.document_reference:
            return

        if not self.document_type:
            frappe.throw("Document Type is required when Document Reference is set.")

        if self.document_type not in ALLOWED_REFERENCE_DOCTYPES:
            frappe.throw(f"Unsupported document type: {self.document_type}")

        reference_doc = frappe.get_doc(self.document_type, self.document_reference)

        if reference_doc.meta.is_submittable and reference_doc.docstatus == 2:
            frappe.throw(f"{self.document_type} {self.document_reference} is Cancelled.")

        reference_qty = _build_qty_map(reference_doc.get("items"))
        ticket_qty = _build_qty_map(self.get("items"))

        extra_items = sorted([item for item in ticket_qty if item not in reference_qty])
        if extra_items:
            frappe.throw(
                f"Items not found in {self.document_type} {self.document_reference}: {', '.join(extra_items)}"
            )

        other_tickets = frappe.get_all(
            "Weighbridge Ticket",
            filters={
                "document_type": self.document_type,
                "document_reference": self.document_reference,
                "name": ["!=", self.name],
                "docstatus": 1
            },
            pluck="name"
        )

        consumed_qty = {}
        if other_tickets:
            other_items = frappe.get_all(
                "Weighbridge Ticket Item",
                filters={"parent": ["in", other_tickets]},
                fields=["item_code", "qty"]
            )
            for row in other_items:
                consumed_qty[row.item_code] = consumed_qty.get(row.item_code, 0) + flt(row.qty)

        for item_code, qty in ticket_qty.items():
            ref_qty = reference_qty.get(item_code, 0)
            cons_qty = consumed_qty.get(item_code, 0)
            available = ref_qty - cons_qty

            if flt(qty) > available:
                frappe.msgprint(
                    f"Quantity {flt(qty)} exceeds remaining available quantity {available} on {self.document_type}.",
                    indicator="orange",
                    alert=True
                )

    def update_reference_document_quantities(self):
        if not self.document_type or not self.document_reference:
            return

        if self.document_type not in ALLOWED_REFERENCE_DOCTYPES:
            frappe.throw(f"Unsupported document type: {self.document_type}")

        reference_doc = frappe.get_doc(self.document_type, self.document_reference)
        if reference_doc.meta.is_submittable and reference_doc.docstatus == 2:
            frappe.throw(f"{self.document_type} {self.document_reference} is Cancelled.")

        ticket_qty = {}
        for row in (self.get("items") or []):
            item_code = (row.get("item_code") or "").strip()
            if item_code:
                ticket_qty[item_code] = flt(row.get("qty"))

        if not ticket_qty:
            frappe.throw("Please add at least one item before submitting Weighbridge Ticket.")

        reference_items = reference_doc.get("items") or []
        reference_codes = {
            (row.get("item_code") or "").strip() for row in reference_items if row.get("item_code")
        }
        missing_items = sorted([item_code for item_code in ticket_qty if item_code not in reference_codes])
        if missing_items:
            frappe.throw(
                f"Items not found in {self.document_type} {self.document_reference}: {', '.join(missing_items)}"
            )

        if reference_doc.meta.is_submittable and reference_doc.docstatus == 0:
            reference_doc.check_permission("write")
            for row in reference_items:
                item_code = (row.get("item_code") or "").strip()
                if item_code in ticket_qty:
                    row.qty = ticket_qty[item_code]
            reference_doc.save()
            return

    def clear_reference_document_link(self):
        pass
