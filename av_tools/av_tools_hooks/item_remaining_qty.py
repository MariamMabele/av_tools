# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

"""Sales Invoice item remaining-quantity validation.

Moved from csf_tz.custom_api. Gated by the AV Tools Settings flag
``enable_validate_item_remaining_qty``: when enabled, a Sales Invoice item
that would oversell available stock (item balance minus pending Sales Orders
and pending direct Sales Invoices) is blocked. Items flagged "Allow Over Sell"
are skipped, as is the whole check when Stock Settings allows negative stock.
"""

from typing import Any

import frappe
from frappe import _
from frappe.query_builder.functions import Sum


def _feature_enabled() -> bool:
	return bool(frappe.db.get_single_value("AV Tools Settings", "enable_validate_item_remaining_qty"))


def get_pending_si_delivery_item_count(item_code, company, warehouse):
	si = frappe.qb.DocType("Sales Invoice")
	sii = frappe.qb.DocType("Sales Invoice Item")
	rows = (
		frappe.qb.from_(sii)
		.join(si)
		.on(si.name == sii.parent)
		.select(
			Sum(sii.delivered_qty).as_("delivered_count"),
			Sum(sii.stock_qty).as_("sold_count"),
		)
		.where(sii.item_code == item_code)
		.where(si.docstatus == 1)
		.where(si.company == company)
		.where(sii.warehouse == warehouse)
		.where(sii.so_detail.isnull())
		.where(sii.so_detail.isnotnull())
		.where(sii.delivery_note.isnotnull())
		.where(si.update_stock == 0)
		.where(sii.is_ignored_in_pending_qty != 1)
		.where(sii.delivered_qty != sii.stock_qty)
		.run(as_dict=True)
	)
	if rows:
		return (rows[0].sold_count or 0) - (rows[0].delivered_count or 0)
	return 0


def get_pending_delivery_item_count(item_code, company, warehouse):
	so = frappe.qb.DocType("Sales Order")
	soi = frappe.qb.DocType("Sales Order Item")
	rows = (
		frappe.qb.from_(soi)
		.join(so)
		.on(so.name == soi.parent)
		.select(
			Sum(soi.delivered_qty).as_("delivered_count"),
			Sum(soi.stock_qty).as_("sold_count"),
		)
		.where(soi.item_code == item_code)
		.where(so.docstatus == 1)
		.where(so.company == company)
		.where(soi.warehouse == warehouse)
		.where(so.status.notin(["Closed", "On Hold", "Cancelled", "Completed"]))
		.run(as_dict=True)
	)
	if rows:
		return (rows[0].sold_count or 0) - (rows[0].delivered_count or 0)
	return 0


def get_item_balance(item_code, company, warehouse=None):
	if company and not warehouse:
		default_warehouse = frappe.get_all(
			"Warehouse", filters={"company": company, "lft": 1}, pluck="name"
		)
		warehouse = default_warehouse[0] if default_warehouse else None

	bin_table = frappe.qb.DocType("Bin")
	query = frappe.qb.from_(bin_table).select(Sum(bin_table.actual_qty)).where(bin_table.item_code == item_code)

	if warehouse:
		lft, rgt, is_group = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt", "is_group"])
		if is_group:
			descendant_warehouses = frappe.get_all(
				"Warehouse", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name"
			)
			query = query.where(bin_table.warehouse.isin(descendant_warehouses or [warehouse]))
		else:
			query = query.where(bin_table.warehouse == warehouse)

	result = query.run()
	return (result[0][0] or 0) if result else 0


@frappe.whitelist()
def validate_item_remaining_qty(
	item_code: Any, company: Any, warehouse: Any = None, stock_qty: Any = None, so_detail: Any = None
):
	if not _feature_enabled():
		return
	if not warehouse or not stock_qty:
		return
	if frappe.db.get_single_value("Stock Settings", "allow_negative_stock"):
		return
	if frappe.get_value("Item", item_code, "is_stock_item") != 1:
		return

	item_balance = get_item_balance(item_code, company, warehouse) or 0
	if not item_balance:
		frappe.throw(
			_("<b>{0}</b> item balance is ZERO. Cannot proceed unless Allow Over Sell").format(item_code)
		)

	pending_delivery = get_pending_delivery_item_count(item_code, company, warehouse) or 0
	pending_si = get_pending_si_delivery_item_count(item_code, company, warehouse) or 0

	if so_detail:
		qty_to_reduce = pending_delivery if pending_delivery > float(stock_qty) else float(stock_qty)
	else:
		qty_to_reduce = pending_delivery + float(stock_qty)

	remaining_qty = item_balance - qty_to_reduce - pending_si
	if remaining_qty < 0:
		frappe.throw(
			_(
				"Item Balance: '{2}'<br>Pending Sales Order: '{3}'<br>Pending Direct Sales Invoice: {5}"
				"<br>Current request is {4}<br><b>Results into balance Qty for '{0}' to '{1}'</b>"
			).format(item_code, remaining_qty, item_balance, pending_delivery, float(stock_qty), pending_si)
		)


def validate_items_remaining_qty(doc, method=None):
	if not _feature_enabled():
		return
	for item in doc.items:
		if not item.allow_over_sell and not (item.so_detail and item.delivery_note):
			validate_item_remaining_qty(
				item.item_code, doc.company, item.warehouse, item.stock_qty, item.so_detail
			)
