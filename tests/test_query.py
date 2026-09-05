import json
import unittest

from lifetxt.parser import parse_text
from lifetxt import query
from lifetxt import saved_views
from tests.test_lifetxt import run_cli


SAMPLE = """#! timezone: UTC
[ ] T Design project:web tag:urgent due:2026-07-01 area:work id:T-1
[x] T Setup project:web tag:home
[ ] T Deploy project:mobile due:2026-09-01 area:work
[ ] T Note1 project:web tag:urgent tag:home
[ ] T FarOut project:web due:2027-01-01
"""


class QueryParseTests(unittest.TestCase):
    def test_explain_query_returns_serializable_plan_and_diagnostics(self):
        explanation = query.explain_query("open project:web due<2026-10-01")

        self.assertEqual("lifetxt-query-explain-v1", explanation["schema"])
        self.assertEqual("open project:web due<2026-10-01", explanation["query"])
        self.assertNotIn("diagnostics", explanation["plan"])
        self.assertTrue(explanation["plan"]["open_only"])
        self.assertEqual(["web"], explanation["plan"]["membership"]["project"])
        self.assertEqual([], explanation["diagnostics"])

    def test_explain_cli_json_does_not_require_a_life_file(self):
        stdout, stderr, code = run_cli(
            "query",
            "open project:web",
            "--explain",
            "--format",
            "json",
        )

        self.assertEqual(0, code, stderr)
        self.assertEqual("", stderr)
        explanation = json.loads(stdout)
        self.assertEqual("lifetxt-query-explain-v1", explanation["schema"])
        self.assertEqual(["web"], explanation["plan"]["membership"]["project"])

    def test_explain_cli_reports_invalid_query_and_keeps_plan(self):
        stdout, stderr, code = run_cli(
            "query", "due:not-a-date", "--explain", "--format", "json"
        )

        self.assertEqual(1, code)
        self.assertEqual("Q002", json.loads(stdout)["diagnostics"][0]["code"])
        self.assertIn("ERROR: Q002", stderr)

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

    def test_progress_percentage_comparison_parsed(self):
        plan, diags = query.parse_query("progress<50%")
        self.assertEqual([], diags)
        self.assertEqual("progress", plan["progress_filters"][0]["field"])
        self.assertEqual("<", plan["progress_filters"][0]["op"])
        self.assertAlmostEqual(0.5, plan["progress_filters"][0]["ratio"])

    def test_progress_fraction_comparison_parsed(self):
        plan, diags = query.parse_query("progress>=3/4")
        self.assertEqual([], diags)
        self.assertAlmostEqual(0.75, plan["progress_filters"][0]["ratio"])

    def test_progress_invalid_value_is_error(self):
        _plan, diags = query.parse_query("progress<nope")
        self.assertEqual("Q005", diags[0]["code"])

    def test_progress_empty_value_warns(self):
        _plan, diags = query.parse_query("progress:")
        self.assertTrue(any(d["code"] == "Q003" for d in diags))

    def test_progress_listed_in_query_fields(self):
        self.assertIn("progress", query.query_fields())


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


PROGRESS_SAMPLE = """#! timezone: UTC
[/] T Low progress:10%
[/] T Mid progress:50%
[/] T High progress:3/4
[/] T NoProgress
[/] T Bad progress:not-a-number
"""


class ProgressQueryApplyTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(PROGRESS_SAMPLE)

    def _run(self, q):
        result, _ = query.run_query(self.items, q, {})
        return [i.title for i in result]

    def test_percentage_less_than(self):
        self.assertEqual(["Low"], self._run("progress<50%"))

    def test_percentage_greater_equal(self):
        self.assertEqual(["Mid", "High"], self._run("progress>=50%"))

    def test_fraction_threshold(self):
        self.assertEqual(["High"], self._run("progress>=3/4"))

    def test_missing_progress_never_matches(self):
        # progress>=0% must not implicitly treat a missing progress: as 0%.
        self.assertNotIn("NoProgress", self._run("progress>=0%"))

    def test_invalid_progress_value_never_matches(self):
        self.assertNotIn("Bad", self._run("progress>=0%"))


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
