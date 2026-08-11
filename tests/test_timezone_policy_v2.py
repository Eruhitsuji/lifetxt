import datetime
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt import timeutil
from lifetxt.timezone_policy import (
    TimezonePolicyError,
    classify_wall_time,
    cli_timezone_candidate_paths,
    comparison_datetime,
    convert_datetime,
    date_boundaries,
    interpret_datetime,
    interpret_time,
    policy_report,
    resolve_timezone_name,
    timezone_context,
)
from tests.timezone_fixture_matrix import (
    DATETIME_NORMALIZATION_CASES,
    TIMEZONE_PRECEDENCE_CASES,
    TIME_ONLY_CASES,
    WALL_TIME_CASES,
)


class TimezonePolicyV2Tests(unittest.TestCase):
    def test_precedence_cli_file_config_host(self):
        for case in TIMEZONE_PRECEDENCE_CASES:
            with self.subTest(case["name"]):
                self.assertEqual(
                    case["expected"],
                    resolve_timezone_name(
                        case["config"], case["text"], case["cli_timezone"]
                    ),
                )

    def test_shared_datetime_normalization_cases(self):
        for case in DATETIME_NORMALIZATION_CASES:
            with self.subTest(case["name"]):
                self.assertEqual(
                    case["expected"],
                    interpret_datetime(case["value"], case["timezone"]).isoformat(),
                )

    def test_aware_datetime_converts_to_resolved_zone(self):
        value = interpret_datetime("2026-07-23T00:00:00+00:00", "Asia/Tokyo")
        self.assertEqual(
            (2026, 7, 23, 9, 0),
            (value.year, value.month, value.day, value.hour, value.minute),
        )
        self.assertEqual(datetime.timedelta(hours=9), value.utcoffset())

    def test_non_hour_offset_is_preserved(self):
        value = interpret_datetime("2026-07-23T12:00", "Asia/Kathmandu")
        self.assertEqual(datetime.timedelta(hours=5, minutes=45), value.utcoffset())

    def test_dst_fold_requires_explicit_policy(self):
        naive = datetime.datetime(2026, 11, 1, 1, 30)
        self.assertEqual(
            "ambiguous", classify_wall_time(naive, "America/New_York")["state"]
        )
        with self.assertRaises(TimezonePolicyError):
            interpret_datetime(naive, "America/New_York")
        earlier = interpret_datetime(naive, "America/New_York", fold_policy="earlier")
        later = interpret_datetime(naive, "America/New_York", fold_policy="later")
        self.assertNotEqual(earlier.utcoffset(), later.utcoffset())
        self.assertLess(
            earlier.astimezone(datetime.timezone.utc),
            later.astimezone(datetime.timezone.utc),
        )

    def test_dst_gap_requires_or_applies_explicit_policy(self):
        naive = datetime.datetime(2026, 3, 8, 2, 30)
        self.assertEqual(
            "nonexistent", classify_wall_time(naive, "America/New_York")["state"]
        )
        with self.assertRaises(TimezonePolicyError):
            interpret_datetime(naive, "America/New_York")
        shifted = interpret_datetime(naive, "America/New_York", gap_policy="next")
        self.assertEqual(3, shifted.hour)
        self.assertEqual(0, shifted.minute)

    def test_time_only_offset_is_anchored_before_conversion(self):
        for case in TIME_ONLY_CASES:
            with self.subTest(case["name"]):
                self.assertEqual(
                    case["expected"],
                    interpret_time(
                        case["value"], case["anchor_date"], case["timezone"]
                    ).isoformat(),
                )

    def test_shared_wall_time_cases_are_reproducible(self):
        for case in WALL_TIME_CASES:
            with self.subTest(case["name"]):
                naive = datetime.datetime.fromisoformat(case["value"])
                self.assertEqual(
                    case["state"], classify_wall_time(naive, case["timezone"])["state"]
                )
                if "error" in case:
                    with self.assertRaisesRegex(TimezonePolicyError, case["error"]):
                        interpret_datetime(naive, case["timezone"])
                if "resolved" in case:
                    for policy, expected_offset in case["resolved"].items():
                        self.assertTrue(
                            interpret_datetime(
                                naive, case["timezone"], fold_policy=policy
                            )
                            .isoformat()
                            .endswith(expected_offset)
                        )
                if "gap_next" in case:
                    self.assertEqual(
                        case["gap_next"],
                        interpret_datetime(
                            naive, case["timezone"], gap_policy="next"
                        ).isoformat(),
                    )

    def test_date_boundaries_are_timezone_aware(self):
        start, end = date_boundaries("2026-07-23", "Asia/Tokyo")
        self.assertEqual((0, 0, 0), (start.hour, start.minute, start.second))
        self.assertEqual(
            (23, 59, 59, 999999), (end.hour, end.minute, end.second, end.microsecond)
        )
        self.assertEqual(datetime.timedelta(hours=9), start.utcoffset())

    def test_comparison_context_changes_aware_wall_clock(self):
        aware = timeutil.parse_datetime("2026-07-23T00:00:00+00:00")
        with timezone_context("Asia/Tokyo"):
            value = comparison_datetime(aware)
            patched = timeutil.comparison_datetime(aware)
        self.assertEqual(9, value.hour)
        self.assertEqual(value, patched)

    def test_convert_naive_uses_explicit_source_timezone(self):
        value = convert_datetime(
            "2026-07-23T09:00",
            timezone_name="UTC",
            source_timezone="Asia/Tokyo",
        )
        self.assertEqual(0, value.hour)
        self.assertEqual(datetime.timedelta(0), value.utcoffset())

    def test_policy_report_documents_naive_aware_and_time_only_rules(self):
        report = policy_report(
            {"defaults": {"timezone": "Asia/Tokyo"}},
            sample="2026-07-23T12:00",
        )
        self.assertTrue(report["valid"])
        self.assertEqual("config", report["source"])
        self.assertIn("naive_values", report)
        self.assertIn("aware_values", report)
        self.assertIn("time_only_values", report)
        self.assertIn("output", report["sample"])


class CliTimezoneCandidatePathsTests(unittest.TestCase):
    """Covers #142: the workspace-aware candidate-file resolver used by the
    CLI's timezone-context bootstrap."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text="[ ] T Task\n"):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def config(self, extra):
        data = OrderedDict(extra)
        data["_path"] = os.path.join(self.root, ".lifetxt.json")
        return data

    def test_legacy_configuration_uses_config_paths_unchanged(self):
        legacy = self.write("legacy.life.txt")
        config = self.config({"paths": [legacy]})
        candidates = cli_timezone_candidate_paths([], config)
        self.assertEqual([legacy], candidates)

    def test_explicit_workspace_uses_its_priority_ordered_input_paths(self):
        low = self.write("low.life.txt")
        high = self.write("high.life.txt")
        config = self.config(
            {
                "workspaces": {
                    "work": {
                        "sources": [
                            {"path": low, "priority": 200},
                            {"path": high, "priority": 10},
                        ]
                    }
                }
            }
        )
        candidates = cli_timezone_candidate_paths([], config, "work")
        self.assertEqual([high, low], candidates)

    def test_implicit_default_workspace_is_used_when_no_explicit_name_given(self):
        target = self.write("default.life.txt")
        config = self.config(
            {
                "default_workspace": "work",
                "workspaces": {"work": {"sources": [target]}},
            }
        )
        candidates = cli_timezone_candidate_paths([], config, None)
        self.assertEqual([target], candidates)

    def test_unknown_workspace_name_falls_back_to_legacy_candidates_instead_of_raising(
        self,
    ):
        legacy = self.write("legacy.life.txt")
        config = self.config(
            {
                "paths": [legacy],
                "workspaces": {"work": {"sources": [self.write("work.life.txt")]}},
            }
        )
        candidates = cli_timezone_candidate_paths([], config, "does-not-exist")
        self.assertEqual([legacy], candidates)

    def test_existing_file_positional_argument_still_takes_precedence(self):
        explicit = self.write("explicit.life.txt")
        workspace_file = self.write("work.life.txt")
        config = self.config({"workspaces": {"work": {"sources": [workspace_file]}}})
        candidates = cli_timezone_candidate_paths([explicit], config, "work")
        self.assertEqual([explicit, workspace_file], candidates)


if __name__ == "__main__":
    unittest.main()
