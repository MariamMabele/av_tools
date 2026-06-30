from unittest import TestCase
from unittest.mock import patch

from av_tools.av_tools_hooks import item_search


class TestItemSearch(TestCase):
	def test_split_search_terms(self):
		self.assertEqual(item_search.split_search_terms("blue chair"), ["blue", "chair"])
		self.assertEqual(item_search.split_search_terms("  blue   chair  "), ["blue", "chair"])
		self.assertEqual(item_search.split_search_terms(""), [])
		self.assertEqual(item_search.split_search_terms(None), [])

	def test_route_item_query(self):
		self.assertEqual(
			item_search.route_item_query("Item", item_search.ERP_ITEM_QUERY),
			item_search.AV_TOOLS_ITEM_QUERY,
		)
		self.assertEqual(item_search.route_item_query("Item", None), item_search.AV_TOOLS_ITEM_QUERY)
		self.assertEqual(
			item_search.route_item_query("Customer", "frappe.desk.search.search_widget"),
			"frappe.desk.search.search_widget",
		)

	def test_item_query_builds_multi_term_conditions(self):
		class Meta:
			def get_search_fields(self):
				return ["item_name", "description"]

		captured = {}

		class FakeDB:
			def exists(self, doctype, name):
				return True

			def count(self, doctype, cache=True):
				return 10

			def sql(self, query, values, as_dict=False):
				captured["query"] = query
				captured["values"] = values
				captured["as_dict"] = as_dict
				return []

		with patch.object(item_search.frappe, "get_meta", return_value=Meta()), patch.object(
			item_search.frappe, "db", FakeDB()
		), patch.object(item_search, "get_filters_cond", return_value=""), patch.object(
			item_search, "get_match_cond", return_value=""
		), patch.object(
			item_search,
			"nowdate",
			return_value="2026-05-13",
		):
			item_search.item_query.__wrapped__(
				doctype="Item",
				txt="blue chair",
				searchfield="name",
				start=0,
				page_len=20,
				filters={},
			)

		self.assertIn("item_name like %(txt_0)s and item_name like %(txt_1)s", captured["query"])
		self.assertIn(
			"tabItem.description like %(txt_0)s and tabItem.description like %(txt_1)s",
			captured["query"],
		)
		self.assertEqual(captured["values"]["txt"], "%blue%chair%")
		self.assertEqual(captured["values"]["_txt"], "blue")
		self.assertEqual(captured["values"]["txt_0"], "%blue%")
		self.assertEqual(captured["values"]["txt_1"], "%chair%")
