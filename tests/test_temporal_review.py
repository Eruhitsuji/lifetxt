import unittest

from lifetxt.parser import parse_text
from lifetxt.temporal_review import build_temporal_review


class TemporalReviewTests(unittest.TestCase):
    def test_empty_period_is_bounded_and_deterministic(self):
        items, diagnostics = parse_text('[ ] T "Open task" id:task-1\n')
        self.assertEqual([], diagnostics)
        result = build_temporal_review(
            items, since="2030-01-01", until="2030-01-07", limit=10
        )
        self.assertEqual("temporal-life-review-v1", result["schema"])
        self.assertEqual(0, result["counts"]["events"])
        self.assertEqual(1, result["counts"]["carry_forward"])

    def test_week_and_explicit_bounds_cannot_be_combined(self):
        items, _ = parse_text('[ ] T "Open task"\n')
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            build_temporal_review(items, since="2030-01-01", week=True)

    def test_date_bounds_use_workspace_timezone_when_requested(self):
        items, _ = parse_text('[ ] T "Open task"\n')
        result = build_temporal_review(
            items,
            since="2030-06-01",
            until="2030-06-01",
            timezone_name="Asia/Tokyo",
        )
        self.assertEqual("2030-06-01T00:00:00+09:00", result["period"]["since"])
        self.assertEqual("2030-06-01T23:59:59.999999+09:00", result["period"]["until"])
