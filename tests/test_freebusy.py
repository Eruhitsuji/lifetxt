"""Unit tests for lifetxt.freebusy's free/busy interval algebra (#673)."""

import datetime
import unittest

from lifetxt.freebusy import compute_freebusy
from lifetxt.parser import parse_text


def _by_id(items, value):
    for item in items:
        if value in item.details.get("id", []):
            return item
    raise AssertionError("no item id:%s" % value)


def _dt(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M")


class ComputeFreebusyBasicsTests(unittest.TestCase):
    def test_no_items_leaves_the_whole_window_free(self):
        result = compute_freebusy([], _dt("2026-08-22T09:00"), _dt("2026-08-22T17:00"))
        self.assertEqual([], result["busy"])
        self.assertEqual(
            [{"start": "2026-08-22T09:00", "end": "2026-08-22T17:00"}], result["free"]
        )
        self.assertEqual([], result["conflicts"])
        self.assertEqual([], result["diagnostics"])

    def test_range_end_not_after_start_is_rejected(self):
        with self.assertRaises(ValueError):
            compute_freebusy([], _dt("2026-08-22T09:00"), _dt("2026-08-22T09:00"))

    def test_window_fully_covered_by_one_event_has_no_free_interval(self):
        items, _ = parse_text(
            "[ ] E All from:2026-08-22T09:00 to:2026-08-22T17:00 id:e1\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T17:00")
        )
        self.assertEqual(1, len(result["busy"]))
        self.assertEqual([], result["free"])

    def test_only_e_and_r_kinds_are_considered(self):
        # A Task carrying from:/to: is not a scheduled occupant of time.
        items, _ = parse_text(
            "[ ] T NotBusy from:2026-08-22T10:00 to:2026-08-22T11:00 id:t1\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T17:00")
        )
        self.assertEqual([], result["busy"])
        self.assertEqual([], result["diagnostics"])

    def test_notify_from_to_and_point_keys_do_not_count_as_busy(self):
        # Reminder windows and deadlines are not attendance; excluded from
        # busy computation but the item still has *some* recognized time
        # detail namespace checked (at/on/from/to), so a Reminder relying
        # only on notify_at is reported missing rather than silently busy.
        items, _ = parse_text(
            "[ ] R Deadline notify_from:2026-08-22T08:00 "
            "notify_to:2026-08-22T09:00 id:r1\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T17:00")
        )
        self.assertEqual([], result["busy"])
        self.assertEqual(
            ["missing_time_detail"], [d["code"] for d in result["diagnostics"]]
        )


class MergeAndOverlapTests(unittest.TestCase):
    def test_non_overlapping_intervals_with_a_real_gap_are_not_merged(self):
        items, _ = parse_text(
            "[ ] E Morning from:2026-08-22T09:00 to:2026-08-22T10:00 id:e1\n"
            "[ ] E Afternoon from:2026-08-22T13:00 to:2026-08-22T14:00 id:e2\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T17:00")
        )
        self.assertEqual(2, len(result["busy"]))
        self.assertEqual(
            [
                {"start": "2026-08-22T10:00", "end": "2026-08-22T13:00"},
                {"start": "2026-08-22T14:00", "end": "2026-08-22T17:00"},
            ],
            result["free"],
        )
        self.assertEqual([], result["conflicts"])

    def test_touching_intervals_merge_into_one_continuous_busy_block(self):
        items, _ = parse_text(
            "[ ] E First from:2026-08-22T09:00 to:2026-08-22T10:00 id:e1\n"
            "[ ] E Second from:2026-08-22T10:00 to:2026-08-22T11:00 id:e2\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T12:00")
        )
        self.assertEqual(
            [{"start": "2026-08-22T11:00", "end": "2026-08-22T12:00"}],
            result["free"],
        )
        # Touching (end == start) is not a genuine overlap.
        self.assertEqual([], result["conflicts"])

    def test_overlapping_events_are_reported_as_a_conflict(self):
        items, _ = parse_text(
            "[ ] E Standup from:2026-08-22T10:00 to:2026-08-22T11:00 id:e1\n"
            "[ ] E Review from:2026-08-22T10:30 to:2026-08-22T11:30 id:e2\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T09:00"), _dt("2026-08-22T18:00")
        )
        self.assertEqual(1, len(result["conflicts"]))
        conflict = result["conflicts"][0]
        self.assertEqual("Standup", conflict["a"]["title"])
        self.assertEqual("Review", conflict["b"]["title"])
        self.assertEqual("2026-08-22T10:30", conflict["start"])
        self.assertEqual("2026-08-22T11:00", conflict["end"])
        # The merged busy region still spans the full union, once.
        self.assertEqual(
            [
                {"start": "2026-08-22T09:00", "end": "2026-08-22T10:00"},
                {"start": "2026-08-22T11:30", "end": "2026-08-22T18:00"},
            ],
            result["free"],
        )

    def test_an_item_never_conflicts_with_its_own_occurrences(self):
        # Two on: dates on the same all-day Event must not self-conflict.
        items, _ = parse_text("[ ] E Trip on:2026-08-22 on:2026-08-23 id:e1\n")
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-24T00:00")
        )
        self.assertEqual([], result["conflicts"])


class ZeroDurationInstantTests(unittest.TestCase):
    def test_at_only_reminder_is_reported_as_an_instant_not_busy(self):
        items, _ = parse_text("[ ] R Ping at:2026-08-22T09:00 id:r1\n")
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-22T23:59")
        )
        self.assertEqual([], result["busy"])
        self.assertEqual(
            [
                {
                    "at": "2026-08-22T09:00",
                    "source_field": "at",
                    "item": {
                        "title": "Ping",
                        "kind": "R",
                        "status": "[ ]",
                        "source": None,
                        "line": 1,
                    },
                }
            ],
            result["instants"],
        )
        # A zero-width instant leaves the whole window free.
        self.assertEqual(
            [{"start": "2026-08-22T00:00", "end": "2026-08-22T23:59"}],
            result["free"],
        )

    def test_from_with_no_matching_to_is_a_point_instant(self):
        items, _ = parse_text("[ ] E Deadline from:2026-08-22T09:00 id:e1\n")
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-22T23:59")
        )
        self.assertEqual([], result["busy"])
        self.assertEqual(1, len(result["instants"]))
        self.assertEqual("from", result["instants"][0]["source_field"])


class DiagnosticsTests(unittest.TestCase):
    def test_invalid_from_value_is_reported_not_silently_ignored(self):
        items, _ = parse_text("[ ] E Bad from:not-a-date id:e1\n")
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-23T00:00")
        )
        self.assertEqual([], result["busy"])
        codes = [d["code"] for d in result["diagnostics"]]
        self.assertIn("invalid_time_value", codes)

    def test_item_with_no_time_detail_is_reported_missing(self):
        items, _ = parse_text("[ ] E Untimed id:e1\n")
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-23T00:00")
        )
        self.assertEqual(
            ["missing_time_detail"], [d["code"] for d in result["diagnostics"]]
        )

    def test_recurring_item_is_skipped_with_a_diagnostic_not_expanded(self):
        items, _ = parse_text(
            "[ ] E Daily from:2026-08-22T09:00 to:2026-08-22T09:30 repeat:daily id:e1\n"
        )
        result = compute_freebusy(
            items, _dt("2026-08-22T00:00"), _dt("2026-08-25T00:00")
        )
        self.assertEqual([], result["busy"])
        self.assertEqual(
            ["skipped_recurring"], [d["code"] for d in result["diagnostics"]]
        )


class DayWindowTests(unittest.TestCase):
    def test_day_window_clips_free_intervals_to_working_hours_each_day(self):
        items, _ = parse_text(
            "[ ] E Standup from:2026-08-22T10:00 to:2026-08-22T10:30 id:e1\n"
        )
        result = compute_freebusy(
            items,
            _dt("2026-08-22T00:00"),
            _dt("2026-08-24T00:00"),
            day_window=(datetime.time(9, 0), datetime.time(17, 0)),
        )
        self.assertEqual(
            [
                {"start": "2026-08-22T09:00", "end": "2026-08-22T10:00"},
                {"start": "2026-08-22T10:30", "end": "2026-08-22T17:00"},
                {"start": "2026-08-23T09:00", "end": "2026-08-23T17:00"},
            ],
            result["free"],
        )

    def test_day_window_does_not_affect_busy_or_conflicts(self):
        items, _ = parse_text(
            "[ ] E Late from:2026-08-22T20:00 to:2026-08-22T21:00 id:e1\n"
        )
        result = compute_freebusy(
            items,
            _dt("2026-08-22T00:00"),
            _dt("2026-08-23T00:00"),
            day_window=(datetime.time(9, 0), datetime.time(17, 0)),
        )
        self.assertEqual(1, len(result["busy"]))
        self.assertEqual("2026-08-22T20:00", result["busy"][0]["start"])


if __name__ == "__main__":
    unittest.main()
