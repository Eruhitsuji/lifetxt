import unittest
from collections import OrderedDict
from datetime import datetime, timedelta

from lifetxt.agenda import item_time_matches
from lifetxt.csvio import items_from_csv_text, items_to_csv
from lifetxt.model import Item
from lifetxt.recurrence import expand, parse_rule
from lifetxt.serializer import (
    items_from_json_text,
    items_from_jsonl_text,
    items_to_json,
    items_to_jsonl,
)
from lifetxt.timer import elapsed_minutes
from lifetxt.timeutil import (
    LifeDateTime,
    comparison_datetime,
    format_datetime,
    parse_date_or_datetime,
    parse_datetime,
)
from lifetxt.validator import validate_item


class TimezoneAwareParsingTests(unittest.TestCase):
    def test_explicit_offset_remains_aware(self):
        parsed = parse_datetime("2026-07-22T09:30:15.25+09:00")
        self.assertIsInstance(parsed, LifeDateTime)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(timedelta(hours=9), parsed.utcoffset())
        self.assertEqual("2026-07-22T09:30:15.25+09:00", format_datetime(parsed))

    def test_z_remains_utc_aware(self):
        parsed = parse_datetime("2026-07-22T00:30Z")
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(timedelta(0), parsed.utcoffset())
        self.assertEqual("2026-07-22T00:30+00:00", format_datetime(parsed))

    def test_compact_offset_is_formatted_canonically(self):
        parsed = parse_datetime("2026-07-22T09:30+0900")
        self.assertEqual(timedelta(hours=9), parsed.utcoffset())
        self.assertEqual("2026-07-22T09:30+09:00", format_datetime(parsed))

    def test_naive_datetime_remains_naive(self):
        parsed = parse_datetime("2026-07-22T09:30")
        self.assertIsNone(parsed.tzinfo)
        self.assertEqual("2026-07-22T09:30", format_datetime(parsed))

    def test_date_boundaries_use_compatible_datetime_type(self):
        start = parse_date_or_datetime("2026-07-22", is_end=False)
        end = parse_date_or_datetime("2026-07-22", is_end=True)
        self.assertIsInstance(start, LifeDateTime)
        self.assertIsInstance(end, LifeDateTime)
        self.assertEqual(datetime(2026, 7, 22, 0, 0), start)
        self.assertEqual(datetime(2026, 7, 22, 23, 59, 59), end)


class TimezoneComparisonTests(unittest.TestCase):
    def test_comparison_normalization_does_not_mutate_aware_value(self):
        aware = parse_datetime("2026-07-22T09:30+09:00")
        normalized = comparison_datetime(aware)
        expected_local = aware.astimezone().replace(tzinfo=None)
        self.assertEqual(expected_local, normalized)
        self.assertEqual(timedelta(hours=9), aware.utcoffset())

    def test_mixed_aware_and_naive_ordering_uses_legacy_local_comparison(self):
        aware = parse_datetime("2026-07-22T09:30+09:00")
        local = comparison_datetime(aware)
        self.assertTrue(aware < local + timedelta(minutes=1))
        self.assertTrue(local + timedelta(minutes=1) > aware)
        self.assertTrue(aware >= local)

    def test_mixed_aware_and_naive_subtraction_is_supported_both_directions(self):
        aware = parse_datetime("2026-07-22T09:30+09:00")
        local = comparison_datetime(aware)
        self.assertEqual(timedelta(minutes=90), (local + timedelta(minutes=90)) - aware)
        self.assertEqual(timedelta(minutes=-90), aware - (local + timedelta(minutes=90)))

    def test_timer_elapsed_math_accepts_legacy_naive_now(self):
        aware = parse_datetime("2026-07-22T09:30+09:00")
        local = comparison_datetime(aware)
        self.assertEqual(90, elapsed_minutes(aware, local + timedelta(minutes=90)))

    def test_agenda_date_range_can_compare_offset_item(self):
        item = Item(
            "[ ]",
            "E",
            "Offset event",
            OrderedDict(
                [
                    ("from", ["2026-07-22T09:30+09:00"]),
                    ("to", ["2026-07-22T10:30+09:00"]),
                ]
            ),
            1,
        )
        start = parse_date_or_datetime("2026-07-21", is_end=False)
        end = parse_date_or_datetime("2026-07-23", is_end=True)
        self.assertTrue(item_time_matches(item, start, end))

    def test_validator_compares_mixed_event_boundaries_without_type_error(self):
        aware = parse_datetime("2026-07-22T09:30+09:00")
        local = comparison_datetime(aware) + timedelta(hours=1)
        item = Item(
            "[ ]",
            "E",
            "Mixed event",
            OrderedDict(
                [
                    ("from", ["2026-07-22T09:30+09:00"]),
                    ("to", [local.strftime("%Y-%m-%dT%H:%M")]),
                ]
            ),
            1,
        )
        diagnostics = validate_item(item)
        self.assertNotIn("W206", [diagnostic.code for diagnostic in diagnostics])


class TimezoneInterchangeTests(unittest.TestCase):
    def setUp(self):
        self.item = Item(
            "[ ]",
            "E",
            "Offset event",
            OrderedDict(
                [
                    ("from", ["2026-07-22T09:30:15.25+09:00"]),
                    ("to", ["2026-07-22T10:45:00+09:00"]),
                ]
            ),
            1,
        )

    def _assert_offsets(self, items):
        self.assertEqual("2026-07-22T09:30:15.25+09:00", items[0].details["from"][0])
        self.assertEqual("2026-07-22T10:45:00+09:00", items[0].details["to"][0])

    def test_json_preserves_offset_strings(self):
        self._assert_offsets(items_from_json_text(items_to_json([self.item])))

    def test_jsonl_preserves_offset_strings(self):
        self._assert_offsets(items_from_jsonl_text(items_to_jsonl([self.item])))

    def test_csv_preserves_offset_strings(self):
        self._assert_offsets(items_from_csv_text(items_to_csv([self.item])))

    def test_simple_recurrence_preserves_offset(self):
        start = parse_datetime("2026-07-22T09:30+09:00")
        occurrences = expand(parse_rule("daily", count=3), start)
        self.assertEqual(3, len(occurrences))
        self.assertTrue(all(value.utcoffset() == timedelta(hours=9) for value in occurrences))
        self.assertEqual(
            [
                "2026-07-22T09:30+09:00",
                "2026-07-23T09:30+09:00",
                "2026-07-24T09:30+09:00",
            ],
            [format_datetime(value) for value in occurrences],
        )


if __name__ == "__main__":
    unittest.main()
