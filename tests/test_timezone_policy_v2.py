import datetime
import unittest

from lifetxt import timeutil
from lifetxt.timezone_policy import (
    TimezonePolicyError,
    classify_wall_time,
    comparison_datetime,
    convert_datetime,
    date_boundaries,
    interpret_datetime,
    interpret_time,
    policy_report,
    resolve_timezone_name,
    timezone_context,
)


class TimezonePolicyV2Tests(unittest.TestCase):
    def test_precedence_cli_file_config_host(self):
        config = {"defaults": {"timezone": "UTC"}}
        text = "#! timezone: Asia/Tokyo\n"
        self.assertEqual(
            "Europe/London", resolve_timezone_name(config, text, "Europe/London")
        )
        self.assertEqual("Asia/Tokyo", resolve_timezone_name(config, text))
        self.assertEqual("UTC", resolve_timezone_name(config, ""))

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
        value = interpret_time("09:15+00:00", "2026-07-23", "Asia/Tokyo")
        self.assertEqual(
            (2026, 7, 23, 18, 15),
            (value.year, value.month, value.day, value.hour, value.minute),
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


if __name__ == "__main__":
    unittest.main()
