"""Approved filter/UNTIL semantics; no generated occurrence violates filters."""

import unittest
from datetime import datetime, timedelta, timezone

from lifetxt import recurrence as R
from lifetxt.agenda import item_time_matches, next_repeat_occurrence
from lifetxt.parser import parse_text
from lifetxt.timezone_policy import timezone_context


class RecurrenceContractTests(unittest.TestCase):
    def test_month_conditions_intersect_and_count_matches(self):
        rule = "RRULE:FREQ=MONTHLY;BYMONTHDAY=31;BYDAY=MO;COUNT=2"
        self.assertEqual(
            ["2031-03-31", "2032-05-31"],
            [x.date().isoformat() for x in R.expand(rule, datetime(2030, 10, 14))],
        )

    def test_positional_conditions_intersect(self):
        rule = "RRULE:FREQ=MONTHLY;BYMONTHDAY=8,9,10,11,12,13,14;BYDAY=2MO"
        self.assertEqual(
            ["2030-10-14", "2030-11-11"],
            [
                x.date().isoformat()
                for x in R.expand(rule, datetime(2030, 10, 14), limit=2)
            ],
        )

    def test_empty_explicit_month_filters_do_not_use_anchor(self):
        for suffix in ("BYDAY=6MO", "BYDAY=-6MO", "BYMONTHDAY=31;BYDAY=2MO"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    [],
                    R.expand(
                        "RRULE:FREQ=MONTHLY;" + suffix,
                        datetime(2030, 10, 14),
                        before=datetime(2030, 11, 30),
                    ),
                )

    def test_short_month_skips_filtered_31_but_clamps_unfiltered(self):
        start = datetime(2030, 1, 31)
        self.assertEqual(
            [31, 31],
            [
                x.day
                for x in R.expand(
                    "RRULE:FREQ=MONTHLY;BYMONTHDAY=31",
                    start,
                    limit=2,
                )
            ],
        )
        self.assertEqual(
            [1, 3],
            [
                x.month
                for x in R.expand(
                    "RRULE:FREQ=MONTHLY;BYMONTHDAY=31",
                    start,
                    limit=2,
                )
            ],
        )
        self.assertEqual(
            [31, 28, 31], [x.day for x in R.expand("monthly", start, limit=3)]
        )

    def test_negative_month_day_intersects_last_friday(self):
        self.assertEqual(
            ["2030-05-31"],
            [
                x.date().isoformat()
                for x in R.expand(
                    "RRULE:FREQ=MONTHLY;BYMONTHDAY=-1;BYDAY=-1FR",
                    datetime(2030, 1, 1),
                    limit=1,
                )
            ],
        )

    def test_yearly_uses_same_intersection_and_empty_behavior(self):
        self.assertEqual(
            [],
            R.expand(
                "RRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=31;BYDAY=MO",
                datetime(2030, 1, 1),
                before=datetime(2032, 12, 31),
            ),
        )

    def test_empty_supported_values_and_list_entries_fail(self):
        for suffix in ("WKST=", "BYMONTHDAY=", "BYDAY=MO,", "BYMONTH=1,,2", "COUNT="):
            with self.subTest(suffix=suffix), self.assertRaises(R.RecurrenceError):
                R.parse_rule("RRULE:FREQ=MONTHLY;" + suffix)

    def test_empty_periods_without_end_stop_before_datetime_overflow(self):
        self.assertEqual(
            [], R.expand("RRULE:FREQ=MONTHLY;BYDAY=6MO", datetime(9999, 12, 1))
        )
        self.assertEqual(
            [],
            R.expand("RRULE:FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=31", datetime(9999, 1, 1)),
        )

    def test_invalid_frequency_combinations_fail(self):
        for rule in ("WEEKLY;BYMONTHDAY=1", "WEEKLY;BYDAY=2MO", "DAILY;BYDAY=-1FR"):
            with self.subTest(rule=rule), self.assertRaises(R.RecurrenceError):
                R.parse_rule("RRULE:FREQ=" + rule)

    def test_sibling_and_rrule_dates_include_fractional_day_end(self):
        for repeat, extra in (
            ("daily", "until:2030-10-14"),
            ("RRULE:FREQ=DAILY;UNTIL=20301014", ""),
        ):
            item = parse_text('[ ] E A on:2030-10-14 repeat:"%s" %s' % (repeat, extra))[
                0
            ][0]
            rule = R.rule_for_item(item)
            self.assertEqual(999999, rule["until"].microsecond)
            self.assertEqual(
                1, len(R.expand(rule, datetime(2030, 10, 14, 23, 59, 59, 500000)))
            )

    def test_until_offsets_are_retained_and_compare_instants(self):
        with timezone_context("UTC"):
            for until in (
                "20301014T120000Z",
                "20301014T210000+0900",
                "2030-10-14T21:00:00+09:00",
            ):
                rule = R.parse_rule("RRULE:FREQ=DAILY;UNTIL=" + until)
                self.assertIsNotNone(rule["until"].tzinfo)
                self.assertEqual(1, len(R.expand(rule, datetime(2030, 10, 14, 12))))
                self.assertEqual(
                    [], R.expand(rule, datetime(2030, 10, 14, 12, 0, 0, 1))
                )

    def test_sibling_until_offset_matches_rrule_and_completion(self):
        with timezone_context("UTC"):
            item = parse_text(
                "[ ] T A due:2030-10-13T12:00 repeat:daily until:2030-10-14T21:00+09:00"
            )[0][0]
            rule = R.rule_for_item(item)
            self.assertEqual(timedelta(hours=9), rule["until"].utcoffset())
            self.assertEqual(
                datetime(2030, 10, 14, 12),
                next_repeat_occurrence(item, "due", datetime(2030, 10, 13).date())[1],
            )
            moments = item_time_matches(
                item, datetime(2030, 10, 13), datetime(2030, 10, 16)
            )
            self.assertEqual(2, len(moments))

    def test_aware_anchor_exact_until_and_count_window(self):
        start = datetime(2030, 10, 14, 21, tzinfo=timezone(timedelta(hours=9)))
        rule = R.parse_rule("RRULE:FREQ=DAILY;COUNT=2;UNTIL=20301015T120000Z")
        with timezone_context("UTC"):
            moments = R.expand(rule, start, after=datetime(2030, 10, 15, 12))
        self.assertEqual([start + timedelta(days=1)], moments)
        self.assertEqual(timedelta(hours=9), moments[0].utcoffset())
