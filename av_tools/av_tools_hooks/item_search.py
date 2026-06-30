import json
import re

import frappe
from frappe import scrub
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.desk.search import search_link as original_search_link
from frappe.desk.search import search_widget as original_search_widget
from frappe.utils import nowdate


ERP_ITEM_QUERY = "erpnext.controllers.queries.item_query"
AV_TOOLS_ITEM_QUERY = "av_tools.av_tools_hooks.item_search.item_query"


def split_search_terms(txt: str | None) -> list[str]:
	if not txt or not isinstance(txt, str):
		return []

	return [part for part in re.split(r"\s+", txt.strip()) if part]


def route_item_query(doctype, query):
	if doctype == "Item" and not query:
		return AV_TOOLS_ITEM_QUERY

	if query == ERP_ITEM_QUERY:
		return AV_TOOLS_ITEM_QUERY

	return query


@frappe.whitelist()
def search_link(
	doctype,
	txt,
	query=None,
	filters=None,
	page_length=10,
	searchfield=None,
	reference_doctype=None,
	ignore_user_permissions=False,
):
	return original_search_link(
		doctype=doctype,
		txt=txt,
		query=route_item_query(doctype, query),
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)


@frappe.whitelist()
def search_widget(
	doctype,
	txt,
	query=None,
	searchfield=None,
	start=0,
	page_length=10,
	filters=None,
	filter_fields=None,
	as_dict=False,
	reference_doctype=None,
	ignore_user_permissions=False,
):
	return original_search_widget(
		doctype=doctype,
		txt=txt,
		query=route_item_query(doctype, query),
		searchfield=searchfield,
		start=start,
		page_length=page_length,
		filters=filters,
		filter_fields=filter_fields,
		as_dict=as_dict,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	doctype = "Item"
	conditions = []
	search_terms = split_search_terms(txt)
	search_text = "%".join(search_terms) if search_terms else ""

	if isinstance(filters, str):
		filters = json.loads(filters)

	meta = frappe.get_meta(doctype, cached=True)
	searchfields = meta.get_search_fields()

	columns = ""
	extra_searchfields = [field for field in searchfields if field not in ["name", "description"]]

	if extra_searchfields:
		columns += ", " + ", ".join(extra_searchfields)

	if "description" in searchfields:
		columns += """, if(length(tabItem.description) > 40, \
			concat(substr(tabItem.description, 1, 40), "..."), description) as description"""

	searchfields = searchfields + [
		field
		for field in [searchfield or "name", "item_code", "item_group", "item_name"]
		if field not in searchfields
	]

	def build_search_condition(field):
		if len(search_terms) <= 1:
			return f"{field} like %(txt)s"

		return "(" + " and ".join([f"{field} like %(txt_{i})s" for i in range(len(search_terms))]) + ")"

	searchfields = " or ".join([build_search_condition(field) for field in searchfields])

	if filters and isinstance(filters, dict):
		if filters.get("customer") or filters.get("supplier"):
			party = filters.get("customer") or filters.get("supplier")
			item_rules_list = frappe.get_all(
				"Party Specific Item",
				filters={"party": party},
				fields=["restrict_based_on", "based_on_value"],
			)

			filters_dict = {}
			for rule in item_rules_list:
				if rule["restrict_based_on"] == "Item":
					rule["restrict_based_on"] = "name"
				filters_dict[rule.restrict_based_on] = []

			for rule in item_rules_list:
				filters_dict[rule.restrict_based_on].append(rule.based_on_value)

			for filter in filters_dict:
				filters[scrub(filter)] = ["in", filters_dict[filter]]

			if filters.get("customer"):
				del filters["customer"]
			else:
				del filters["supplier"]
		else:
			filters.pop("customer", None)
			filters.pop("supplier", None)

	description_cond = ""
	if frappe.db.count(doctype, cache=True) < 50000:
		description_cond = f"or {build_search_condition('tabItem.description')}"

	return frappe.db.sql(
		"""select
			tabItem.name {columns}
		from tabItem
		where tabItem.docstatus < 2
			and tabItem.disabled=0
			and tabItem.has_variants=0
			and (tabItem.end_of_life > %(today)s or ifnull(tabItem.end_of_life, '0000-00-00')='0000-00-00')
			and ({scond} or tabItem.item_code IN (select parent from `tabItem Barcode` where barcode LIKE %(txt)s)
				{description_cond})
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, item_name), locate(%(_txt)s, item_name), 99999),
			idx desc,
			name, item_name
		limit %(start)s, %(page_len)s """.format(
			columns=columns,
			scond=searchfields,
			fcond=get_filters_cond(doctype, filters, conditions).replace("%", "%%"),
			mcond=get_match_cond(doctype).replace("%", "%%"),
			description_cond=description_cond,
		),
		{
			"today": nowdate(),
			"txt": f"%{search_text}%",
			"_txt": (search_terms[0] if search_terms else "").replace("%", ""),
			"start": start,
			"page_len": page_len,
			**{f"txt_{i}": f"%{term}%" for i, term in enumerate(search_terms)},
		},
		as_dict=as_dict,
	)
