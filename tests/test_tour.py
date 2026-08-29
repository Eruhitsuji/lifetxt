"""Unit coverage for `lifetxt.tour` (#590): the zero-config first-run tour.

These tests exercise the pure/testable functions directly with an injected
reference date, so they stay deterministic regardless of the day they run.
"""

import datetime
import unittest

from lifetxt.command_center import command_center
from lifetxt.tour import (
    build_tour_sample,
    render_tour_json,
    render_tour_text,
    tour_report,
)


class BuildTourSampleTests(unittest.TestCase):
    def test_sample_uses_only_the_beginner_profile_vocabulary(self):
        reference_date = datetime.date(2026, 3, 5)
        source_text, items = build_tour_sample(reference_date)

        self.assertIn("due:2026-03-05", source_text)
        self.assertIn("from:2026-03-06T10:00", source_text)
        self.assertIn("to:2026-03-06T10:30", source_text)

        kinds = sorted(item.kind for item in items)
        self.assertEqual(["E", "N", "T"], kinds)
        for item in items:
            self.assertIn(item.status, ("[ ]", "[N]"))

    def test_sample_parses_with_no_diagnostics(self):
        from lifetxt.parser import parse_text

        source_text, _items = build_tour_sample(datetime.date(2026, 3, 5))
        _items, diagnostics = parse_text(source_text)
        self.assertEqual([], diagnostics)

    def test_sample_is_deterministic_for_the_same_reference_date(self):
        reference_date = datetime.date(2026, 3, 5)
        first_text, _first_items = build_tour_sample(reference_date)
        second_text, _second_items = build_tour_sample(reference_date)
        self.assertEqual(first_text, second_text)


class TourReportTests(unittest.TestCase):
    def test_report_matches_a_direct_command_center_call(self):
        """The tour must reuse command_center unmodified -- not reimplement
        due/agenda/business rules of its own."""
        reference_date = datetime.date(2026, 3, 5)
        returned_date, source_text, report = tour_report(reference_date)
        self.assertEqual(reference_date, returned_date)

        _source_text, items = build_tour_sample(reference_date)
        expected = command_center(items, {}, reference_date)
        self.assertEqual(expected, report)

    def test_the_task_appears_due_today_when_run_on_its_own_due_date(self):
        reference_date = datetime.date(2026, 3, 5)
        _date, _source_text, report = tour_report(reference_date)
        self.assertEqual(1, len(report["due_today"]))
        self.assertEqual("Buy milk", report["due_today"][0]["title"])
        self.assertEqual([], report["overdue"])

    def test_defaults_to_the_real_current_date_when_omitted(self):
        from lifetxt.timezone_policy import today as timezone_today

        returned_date, _source_text, _report = tour_report()
        self.assertEqual(timezone_today(), returned_date)

    def test_tour_report_performs_no_filesystem_writes(self):
        """command_center never writes; confirm the tour's own composition
        of it introduces no write either, by running from a directory this
        test does not create any file in."""
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            before = set(os.listdir(temp_dir))
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                tour_report(datetime.date(2026, 3, 5))
            finally:
                os.chdir(cwd)
            after = set(os.listdir(temp_dir))
        self.assertEqual(before, after)


class RenderTourTextTests(unittest.TestCase):
    def test_text_output_contains_the_sample_and_next_steps(self):
        reference_date = datetime.date(2026, 3, 5)
        _date, source_text, report = tour_report(reference_date)
        text = render_tour_text(reference_date, source_text, report)

        self.assertIn('"Buy milk"', text)
        self.assertIn('"Team meeting"', text)
        self.assertIn('"Idea"', text)
        self.assertIn("Due today (1):", text)
        self.assertIn("lifetxt init", text)
        self.assertIn("lifetxt today", text)
        self.assertIn("2026-03-05", text)

    def test_text_output_is_deterministic_for_a_fixed_reference_date(self):
        reference_date = datetime.date(2026, 3, 5)
        _date, source_text, report = tour_report(reference_date)
        first = render_tour_text(reference_date, source_text, report)
        second = render_tour_text(reference_date, source_text, report)
        self.assertEqual(first, second)

    def test_text_output_stays_small(self):
        """Must not resemble the full 30-record `demo` dataset."""
        reference_date = datetime.date(2026, 3, 5)
        _date, source_text, report = tour_report(reference_date)
        text = render_tour_text(reference_date, source_text, report)
        self.assertLess(len(text.splitlines()), 30)


class RenderTourJsonTests(unittest.TestCase):
    def test_json_output_round_trips_the_reference_date_and_report(self):
        import json

        reference_date = datetime.date(2026, 3, 5)
        _date, source_text, report = tour_report(reference_date)
        payload = json.loads(render_tour_json(reference_date, source_text, report))
        self.assertEqual("2026-03-05", payload["reference_date"])
        self.assertEqual(source_text, payload["sample"])
        self.assertEqual(report, payload["today"])


if __name__ == "__main__":
    unittest.main()
