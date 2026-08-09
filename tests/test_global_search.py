import os
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt import global_search, inbox


CONFIG = {
    "groups": {"eng": {"members": ["alice", "bob"], "aliases": ["engineering"]}},
    "projects": {"web": {"display_name": "Website Revamp"}},
}

SAMPLE = """#! timezone: UTC
[N] N Website record:project project:web owner:alice area:work
[ ] T Design project:web assignee:alice url:https://example.com/webapp id:T1
[ ] N Meeting_notes body:discussed_the_roadmap project:web id:N1
[ ] T Other project:mobile area:home
"""


class GlobalSearchTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def search(self, term, **kw):
        return global_search.global_search(self.items, CONFIG, term, **kw)

    def test_item_title_match(self):
        result = self.search("design")
        names = [r["name"] for r in result["groups"]["item"]]
        self.assertIn("T1", names)

    def test_item_detail_match(self):
        result = self.search("example.com")
        row = result["groups"]["item"][0]
        self.assertEqual("url", row["field"])

    def test_body_match(self):
        result = self.search("roadmap")
        names = [r["name"] for r in result["groups"]["item"]]
        self.assertIn("N1", names)

    def test_project_match(self):
        result = self.search("revamp")
        self.assertEqual("web", result["groups"]["project"][0]["name"])

    def test_person_match(self):
        result = self.search("alice")
        self.assertIn("person", result["groups"])
        self.assertEqual("alice", result["groups"]["person"][0]["name"])

    def test_group_match_by_name_and_alias(self):
        self.assertIn(
            "group",
            self.search("eng").groups if False else self.search("eng")["groups"],
        )
        result = self.search("engineering")
        self.assertEqual("eng", result["groups"]["group"][0]["name"])

    def test_group_match_by_member(self):
        result = self.search("bob", types=["group"])
        self.assertEqual("member", result["groups"]["group"][0]["field"])

    def test_area_match(self):
        result = self.search("home")
        self.assertIn("area", result["groups"])

    def test_type_filter(self):
        result = self.search("web", types=["project"])
        self.assertEqual(["project"], list(result["groups"].keys()))

    def test_limit_per_type(self):
        result = self.search("project", types=["item"], limit=1)
        self.assertLessEqual(len(result["groups"].get("item", [])), 1)

    def test_empty_term_returns_nothing(self):
        result = self.search("")
        self.assertEqual(0, result["total"])

    def test_no_match(self):
        result = self.search("zzzznomatch")
        self.assertEqual(0, result["total"])

    def test_flatten(self):
        result = self.search("alice")
        rows = global_search.flatten(result)
        self.assertEqual(result["total"], len(rows))


class GlobalSearchFuzzyTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def search(self, term, **kw):
        return global_search.global_search(self.items, CONFIG, term, **kw)

    def test_default_behavior_is_unaffected_by_a_typo(self):
        # "Desgin" is a transposed typo for "Design" (T1's title).
        self.assertEqual(0, self.search("Desgin")["total"])

    def test_fuzzy_true_matches_a_typo(self):
        result = self.search("Desgin", fuzzy=True)
        names = [r["name"] for r in result["groups"].get("item", [])]
        self.assertIn("T1", names)

    def test_fuzzy_true_ranks_exact_matches_before_approximate_ones(self):
        # T1's title is an exact substring match for "design"; T2's is only
        # a near miss (a deleted letter) and must be ranked after it.
        items, diagnostics = parse_text("[ ] T Design id:T1\n[ ] T Desgn id:T2\n")
        self.assertEqual([], diagnostics)
        result = global_search.global_search(items, CONFIG, "design", fuzzy=True)
        names = [r["name"] for r in result["groups"]["item"]]
        self.assertEqual(["T1", "T2"], names)

    def test_fuzzy_true_is_deterministic(self):
        first = self.search("Desgin", fuzzy=True)
        second = self.search("Desgin", fuzzy=True)
        self.assertEqual(first, second)

    def test_fuzzy_defaults_to_false(self):
        self.assertEqual(self.search("Desgin"), self.search("Desgin", fuzzy=False))


class GlobalSearchProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = dict(CONFIG)
        self.config["inbox"] = {
            "proposals_file": os.path.join(self.temp.name, "p.json")
        }
        self.items, _ = parse_text(SAMPLE)

    def tearDown(self):
        self.temp.cleanup()

    def test_proposal_match(self):
        inbox.stage_create(self.config, "Buy widgets", details={"project": "web"})
        result = global_search.global_search(self.items, self.config, "widgets")
        self.assertIn("proposal", result["groups"])


if __name__ == "__main__":
    unittest.main()
