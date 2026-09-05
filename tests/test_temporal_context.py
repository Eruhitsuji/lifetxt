import datetime
import unittest

from lifetxt.parser import parse_text
from lifetxt.temporal_context import node_facts, temporal_context
from lifetxt.ticket_project_values import reference_time


TODAY = datetime.date(2026, 8, 22)

# node_facts() deliberately compares staleness against the real wall clock
# (reference_time(None), matching ticket_project_report.py's own design),
# not against the fixed TODAY constant above -- so t6/t7's `updated:` values
# must be derived relative to the real clock at test-run time rather than
# fixed calendar dates, or this fixture becomes a time bomb as real time
# passes (#661).
_REAL_TODAY = reference_time(None).date()
_STALE_UPDATED = (_REAL_TODAY - datetime.timedelta(days=400)).isoformat()
_FRESH_UPDATED = (_REAL_TODAY - datetime.timedelta(days=1)).isoformat()

SAMPLE = """#! timezone: UTC
[ ] T Overdue due:2026-08-20 id:t1
[ ] T DueToday due:2026-08-22 id:t2
[ ] T Soon due:2026-08-23 id:t3
[ ] T FarOut due:2026-09-15 id:t4
[ ] T NoDate id:t5
[ ] T Stale updated:{stale} id:t6
[ ] T Fresh updated:{fresh} id:t7
""".format(stale=_STALE_UPDATED, fresh=_FRESH_UPDATED)


def _by_id(items, value):
    for item in items:
        if value in item.details.get("id", []):
            return item
    raise AssertionError("no item id:%s" % value)


class NodeFactsTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_overdue_item_reports_overdue_by(self):
        target = _by_id(self.items, "t1")
        facts = node_facts(target, TODAY)
        self.assertEqual(
            [("overdue_by", "due", 2)],
            [(f["rule"], f["source_field"], f["days"]) for f in facts],
        )

    def test_due_today_reports_zero_day_due_in(self):
        target = _by_id(self.items, "t2")
        facts = node_facts(target, TODAY)
        self.assertEqual(
            [("due_in", "due", 0)],
            [(f["rule"], f["source_field"], f["days"]) for f in facts],
        )

    def test_future_due_reports_due_in(self):
        target = _by_id(self.items, "t3")
        facts = node_facts(target, TODAY)
        self.assertEqual(
            [("due_in", "due", 1)],
            [(f["rule"], f["source_field"], f["days"]) for f in facts],
        )

    def test_item_with_no_date_produces_no_due_fact(self):
        target = _by_id(self.items, "t5")
        facts = node_facts(target, TODAY)
        self.assertEqual([], facts)

    def test_stale_item_reports_stale_since_using_the_shared_threshold(self):
        target = _by_id(self.items, "t6")
        facts = node_facts(target, TODAY, stale_after_days=14)
        rules = [f["rule"] for f in facts]
        self.assertIn("stale_since", rules)
        stale = next(f for f in facts if f["rule"] == "stale_since")
        self.assertEqual(14, stale["threshold_days"])
        self.assertGreater(stale["days"], 14)

    def test_recently_updated_item_is_not_stale(self):
        target = _by_id(self.items, "t7")
        facts = node_facts(target, TODAY, stale_after_days=14)
        self.assertEqual([], [f for f in facts if f["rule"] == "stale_since"])

    def test_custom_stale_after_days_changes_the_threshold(self):
        target = _by_id(self.items, "t7")
        # Fresh was updated one day before the real clock at test-run time,
        # and node_facts uses the real clock for staleness (matching
        # ticket_project_report.py's own reference_time(None) behavior), so
        # a very small threshold still trips it deterministically.
        facts = node_facts(target, TODAY, stale_after_days=0)
        self.assertTrue(any(f["rule"] == "stale_since" for f in facts))


class TemporalContextTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_related_items_are_bounded_to_the_window_and_sorted_nearest_first(self):
        target = _by_id(self.items, "t1")
        context = temporal_context(self.items, target, TODAY, window_days=7)
        self.assertEqual(
            ["t2", "t3"], [edge["target_id"] for edge in context["related"]]
        )
        # t4 (2026-09-15) is far outside the 7-day window from t1's due date.
        self.assertNotIn("t4", [edge["target_id"] for edge in context["related"]])

    def test_related_relation_labels_reflect_direction(self):
        target = _by_id(self.items, "t2")
        context = temporal_context(self.items, target, TODAY, window_days=7)
        by_id = {edge["target_id"]: edge for edge in context["related"]}
        self.assertEqual("before", by_id["t1"]["relation"])
        self.assertEqual("after", by_id["t3"]["relation"])

    def test_same_day_relation_when_dates_match(self):
        items, _ = parse_text(
            "#! timezone: UTC\n"
            "[ ] T A due:2026-08-22 id:a1\n"
            "[ ] T B due:2026-08-22 id:a2\n"
        )
        target = _by_id(items, "a1")
        context = temporal_context(items, target, TODAY, window_days=1)
        self.assertEqual(1, len(context["related"]))
        self.assertEqual("same_day", context["related"][0]["relation"])
        self.assertEqual(0, context["related"][0]["days"])

    def test_limit_bounds_the_related_list_without_dropping_the_nearest(self):
        items, _ = parse_text(
            "#! timezone: UTC\n"
            "[ ] T Target due:2026-08-22 id:target\n"
            "[ ] T N1 due:2026-08-23 id:n1\n"
            "[ ] T N2 due:2026-08-24 id:n2\n"
            "[ ] T N3 due:2026-08-25 id:n3\n"
        )
        target = _by_id(items, "target")
        context = temporal_context(items, target, TODAY, window_days=7, limit=2)
        self.assertEqual(2, len(context["related"]))
        self.assertEqual(["n1", "n2"], [e["target_id"] for e in context["related"]])

    def test_target_with_no_date_has_no_related_items(self):
        target = _by_id(self.items, "t5")
        context = temporal_context(self.items, target, TODAY, window_days=30)
        self.assertEqual([], context["related"])

    def test_result_carries_the_canonical_schema_marker_and_target_identity(self):
        target = _by_id(self.items, "t1")
        context = temporal_context(self.items, target, TODAY)
        self.assertEqual("temporal-context-v1", context["schema"])
        self.assertEqual("t1", context["target_id"])
        self.assertEqual("Overdue", context["target"]["title"])
        self.assertEqual("2026-08-22", context["reference_date"])

    def test_every_fact_and_edge_carries_provenance(self):
        target = _by_id(self.items, "t1")
        context = temporal_context(self.items, target, TODAY)
        for fact in context["facts"]:
            self.assertIn("rule", fact)
            self.assertIn("source_field", fact)
            self.assertIn("reference_time", fact)
        for edge in context["related"]:
            self.assertIn("rule", edge)
            self.assertIn("source_field", edge)
            self.assertIn("reference_time", edge)

    def test_done_and_cancelled_items_still_participate_in_pure_date_ordering(self):
        items, _ = parse_text(
            "#! timezone: UTC\n"
            "[ ] T Open due:2026-08-22 id:o1\n"
            "[x] T Done due:2026-08-22 id:d1 done:2026-08-20\n"
        )
        target = _by_id(items, "o1")
        context = temporal_context(items, target, TODAY, window_days=1)
        self.assertEqual(["d1"], [e["target_id"] for e in context["related"]])


if __name__ == "__main__":
    unittest.main()
