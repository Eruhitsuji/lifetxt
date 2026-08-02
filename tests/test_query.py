import unittest

from lifetxt.parser import parse_text
from lifetxt import query
from lifetxt import saved_views


SAMPLE = """#! timezone: UTC
[ ] T Design project:web tag:urgent due:2026-07-01 area:work id:T-1
[x] T Setup project:web tag:home
[ ] T Deploy project:mobile due:2026-09-01 area:work
[ ] T Note1 project:web tag:urgent tag:home
[ ] T FarOut project:web due:2027-01-01
"""


class QueryParseTests(unittest.TestCase):
    def test_membership_and_open_flag(self):
        plan, diags = query.parse_query("open project:web tag:urgent")
        self.assertTrue(plan["open_only"])
        self.assertEqual(["web"], plan["membership"]["project"])
        self.assertEqual(["urgent"], plan["membership"]["tag"])
        self.assertEqual([], diags)

    def test_comma_values_are_or(self):
        plan, _ = query.parse_query("tag:urgent,home")
        self.assertEqual(["urgent", "home"], plan["membership"]["tag"])

    def test_date_comparison_parsed(self):
        plan, diags = query.parse_query("due<2026-08-01")
        self.assertEqual([], diags)
        self.assertEqual("due", plan["date_filters"][0]["field"])
        self.assertEqual("<", plan["date_filters"][0]["op"])

    def test_invalid_date_is_error(self):
        _plan, diags = query.parse_query("due<nope")
        self.assertEqual("Q002", diags[0]["code"])

    def test_unknown_field_warns(self):
        _plan, diags = query.parse_query("bogus:x")
        self.assertEqual("Q001", diags[0]["code"])

    def test_empty_value_warns(self):
        _plan, diags = query.parse_query("project:")
        self.assertTrue(any(d["code"] == "Q003" for d in diags))

    def test_exclude_tag_forms(self):
        plan, _ = query.parse_query("-tag:home exclude_tag:archived")
        self.assertIn("home", plan["excludes"])
        self.assertIn("archived", plan["excludes"])

    def test_custom_detail_area_routed(self):
        plan, diags = query.parse_query("area:work")
        self.assertEqual(["work"], plan["details"]["area"])
        self.assertEqual([], diags)

    def test_bad_operator_for_membership(self):
        _plan, diags = query.parse_query("project<web")
        self.assertEqual("Q004", diags[0]["code"])

    def test_quoted_text(self):
        plan, _ = query.parse_query('text:"buy milk" project:web')
        self.assertIn("buy milk", plan["text"])


class QueryApplyTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def _run(self, q, **kw):
        result, _ = query.run_query(self.items, q, {}, **kw)
        return [i.title for i in result]

    def test_open_project_membership(self):
        self.assertEqual(["Design", "Note1", "FarOut"], self._run("open project:web"))

    def test_tag_filter(self):
        self.assertEqual(["Design", "Note1"], self._run("tag:urgent"))

    def test_date_before(self):
        self.assertEqual(["Design"], self._run("due<2026-08-01"))

    def test_date_after(self):
        self.assertEqual(["Deploy", "FarOut"], self._run("due>2026-08-01"))

    def test_area_detail_or(self):
        self.assertEqual(["Design", "Deploy"], self._run("area:work"))

    def test_exclude_tag(self):
        # Note1 has both urgent and home; excluding home drops it.
        self.assertEqual(["Design"], self._run("tag:urgent -tag:home"))

    def test_sort_and_limit(self):
        titles = self._run("project:web", sort="due", limit=2)
        self.assertEqual(2, len(titles))

    def test_text_search(self):
        self.assertEqual(["Design"], self._run("text:Design"))


class SavedViewTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)
        self.config = {
            "saved_views": {
                "web_open": {"query": "open project:web", "sort": "due", "limit": 10},
                "urgent": "tag:urgent",
            }
        }

    def test_list_and_normalize(self):
        views = {v["name"]: v for v in saved_views.list_saved_views(self.config)}
        self.assertEqual("open project:web", views["web_open"]["query"])
        self.assertEqual(["due"], views["web_open"]["sort"])
        self.assertEqual("tag:urgent", views["urgent"]["query"])  # string shorthand

    def test_run_saved_view(self):
        result, _ = saved_views.run_saved_view(self.items, self.config, "urgent")
        self.assertEqual(["Design", "Note1"], [i.title for i in result])

    def test_unknown_view_raises(self):
        with self.assertRaises(ValueError):
            saved_views.get_saved_view(self.config, "nope")

    def test_validate_reports_bad_query(self):
        rows = saved_views.validate_saved_views(
            {"saved_views": {"bad": {"query": "due<xx"}}}
        )
        self.assertEqual("V002", rows[0]["code"])

    def test_validate_reports_empty_query(self):
        rows = saved_views.validate_saved_views(
            {"saved_views": {"empty": {"query": ""}}}
        )
        self.assertEqual("V001", rows[0]["code"])

    def test_list_form_supported(self):
        config = {"saved_views": [{"name": "a", "query": "open"}]}
        views = saved_views.list_saved_views(config)
        self.assertEqual("a", views[0]["name"])


if __name__ == "__main__":
    unittest.main()
