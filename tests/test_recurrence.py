"""Tests for recurrence rule parsing and expansion."""

import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime

from lifetxt import recurrence as R
from lifetxt.agenda import agenda_records, item_time_matches, next_repeat_occurrence
from lifetxt.parser import parse_text


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONDAY = datetime(2026, 7, 20, 9, 0)


def _days(moments):
    return [moment.date().isoformat() for moment in moments]


class ParseTests(unittest.TestCase):
    def test_plain_names(self):
        for name in ("daily", "weekly", "monthly", "yearly"):
            rule = R.parse_rule(name)
            self.assertEqual(name, rule["name"])
            self.assertEqual(1, rule["interval"])

    def test_rrule_parts(self):
        rule = R.parse_rule("RRULE:FREQ=WEEKLY;INTERVAL=2;COUNT=5;BYDAY=MO,WE")

        self.assertEqual("weekly", rule["name"])
        self.assertEqual(2, rule["interval"])
        self.assertEqual(5, rule["count"])
        self.assertEqual(((0, 0), (0, 2)), rule["byday"])

    def test_positional_byday(self):
        self.assertEqual(((1, 0),), R.parse_rule("RRULE:FREQ=MONTHLY;BYDAY=1MO")["byday"])
        self.assertEqual(((-1, 4),), R.parse_rule("RRULE:FREQ=MONTHLY;BYDAY=-1FR")["byday"])

    def test_bymonthday_and_bymonth(self):
        rule = R.parse_rule("RRULE:FREQ=YEARLY;BYMONTH=1,7;BYMONTHDAY=1,-1")

        self.assertEqual((1, 7), rule["bymonth"])
        self.assertEqual((-1, 1), rule["bymonthday"])

    def test_until_accepts_several_forms(self):
        for text in ("20260725", "20260725T120000Z", "2026-07-25", "2026-07-25T12:00"):
            rule = R.parse_rule("RRULE:FREQ=DAILY;UNTIL=%s" % text)
            self.assertEqual(date(2026, 7, 25), rule["until"].date(), text)

    def test_date_only_until_covers_the_whole_day(self):
        # Midnight would drop an occurrence happening later on the final day.
        rule = R.parse_rule("RRULE:FREQ=DAILY;UNTIL=20260725")

        self.assertEqual(23, rule["until"].hour)
        self.assertEqual(datetime(2026, 7, 25, 12, 0), R.parse_rule(
            "RRULE:FREQ=DAILY;UNTIL=2026-07-25T12:00")["until"])

    def test_sibling_details_fill_missing_parts(self):
        rule = R.parse_rule("weekly", interval=3, count=4, until=datetime(2027, 1, 1))

        self.assertEqual(3, rule["interval"])
        self.assertEqual(4, rule["count"])
        self.assertEqual(datetime(2027, 1, 1), rule["until"])

    def test_rule_parts_win_over_sibling_details(self):
        rule = R.parse_rule("RRULE:FREQ=DAILY;INTERVAL=5", interval=2)

        self.assertEqual(5, rule["interval"])

    def test_unsupported_parts_are_reported_not_dropped(self):
        rule = R.parse_rule("RRULE:FREQ=WEEKLY;BYDAY=MO;BYSETPOS=1;BYHOUR=9")

        self.assertEqual(["BYSETPOS", "BYHOUR"], rule["unsupported"])

    def test_bad_rules_fail_loudly(self):
        for text in (
            "",
            "nonsense",
            "RRULE:FREQ=HOURLY",
            "RRULE:BYDAY=MO",
            "RRULE:FREQ=WEEKLY;BYDAY=XX",
            "RRULE:FREQ=WEEKLY;BYDAY=0MO",
            "RRULE:FREQ=DAILY;INTERVAL=0",
            "RRULE:FREQ=DAILY;INTERVAL=abc",
            "RRULE:FREQ=DAILY;UNTIL=oops",
            "RRULE:FREQ=MONTHLY;BYMONTHDAY=45",
            "RRULE:FREQ=YEARLY;BYMONTH=13",
            "RRULE:FREQ=DAILY;JUNK",
        ):
            with self.assertRaises(R.RecurrenceError, msg=text):
                R.parse_rule(text)


class ExpansionTests(unittest.TestCase):
    def test_daily_and_interval(self):
        self.assertEqual(
            ["2026-07-20", "2026-07-21", "2026-07-22"], _days(R.expand("daily", MONDAY, limit=3))
        )
        self.assertEqual(
            ["2026-07-20", "2026-07-23", "2026-07-26"],
            _days(R.expand("RRULE:FREQ=DAILY;INTERVAL=3", MONDAY, limit=3)),
        )

    def test_weekly_byday(self):
        moments = R.expand("RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR", MONDAY, limit=4)

        self.assertEqual(["2026-07-20", "2026-07-22", "2026-07-24", "2026-07-27"], _days(moments))

    def test_weekly_interval_skips_weeks(self):
        moments = R.expand("RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU", MONDAY, limit=3)

        self.assertEqual(["2026-07-21", "2026-08-04", "2026-08-18"], _days(moments))

    def test_monthly_positional_byday(self):
        first = R.expand("RRULE:FREQ=MONTHLY;BYDAY=1MO", MONDAY, limit=3)
        last = R.expand("RRULE:FREQ=MONTHLY;BYDAY=-1FR", MONDAY, limit=3)

        self.assertEqual(["2026-08-03", "2026-09-07", "2026-10-05"], _days(first))
        self.assertEqual(["2026-07-31", "2026-08-28", "2026-09-25"], _days(last))
        for moment in first:
            self.assertEqual(0, moment.weekday())
        for moment in last:
            self.assertEqual(4, moment.weekday())

    def test_monthly_bymonthday_including_end_of_month(self):
        self.assertEqual(
            ["2026-08-01", "2026-08-15", "2026-09-01"],
            _days(R.expand("RRULE:FREQ=MONTHLY;BYMONTHDAY=1,15", MONDAY, limit=3)),
        )
        self.assertEqual(
            ["2026-07-31", "2026-08-31", "2026-09-30"],
            _days(R.expand("RRULE:FREQ=MONTHLY;BYMONTHDAY=-1", MONDAY, limit=3)),
        )

    def test_monthly_anchor_day_clamps_on_short_months(self):
        moments = R.expand("monthly", datetime(2026, 1, 31), limit=4)

        self.assertEqual(["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"], _days(moments))

    def test_yearly_bymonth_is_not_skipped(self):
        # Stepping 12 months at a time would never leave the anchor's month.
        moments = R.expand("RRULE:FREQ=YEARLY;BYMONTH=1;BYMONTHDAY=1", MONDAY, limit=3)

        self.assertEqual(["2027-01-01", "2028-01-01", "2029-01-01"], _days(moments))

    def test_yearly_with_several_months(self):
        moments = R.expand("RRULE:FREQ=YEARLY;BYMONTH=3,9;BYMONTHDAY=1", MONDAY, limit=3)

        self.assertEqual(["2026-09-01", "2027-03-01", "2027-09-01"], _days(moments))

    def test_count_and_until_bound_the_series(self):
        self.assertEqual(3, len(R.expand("RRULE:FREQ=DAILY;COUNT=3", MONDAY)))
        self.assertEqual(
            ["2026-07-20", "2026-07-21", "2026-07-22"],
            _days(R.expand("RRULE:FREQ=DAILY;UNTIL=20260722", MONDAY)),
        )

    def test_count_is_measured_from_the_series_start(self):
        # A windowed view must still reflect where the series really ends.
        moments = R.expand("RRULE:FREQ=DAILY;COUNT=3", MONDAY, after=datetime(2026, 7, 21))

        self.assertEqual(["2026-07-21", "2026-07-22"], _days(moments))

    def test_window_filters_without_shifting_the_phase(self):
        moments = R.expand(
            "RRULE:FREQ=WEEKLY;BYDAY=MO,FR",
            MONDAY,
            after=datetime(2026, 8, 1),
            before=datetime(2026, 8, 15),
        )

        self.assertEqual(["2026-08-03", "2026-08-07", "2026-08-10", "2026-08-14"], _days(moments))

    def test_unbounded_rules_stop_at_a_ceiling(self):
        self.assertEqual(R.DEFAULT_MAX_OCCURRENCES, len(R.expand("daily", MONDAY)))

    def test_expansion_preserves_the_time_of_day(self):
        moments = R.expand("RRULE:FREQ=WEEKLY;BYDAY=WE", datetime(2026, 7, 20, 14, 30), limit=2)

        for moment in moments:
            self.assertEqual((14, 30), (moment.hour, moment.minute))

    def test_expansion_requires_a_start(self):
        with self.assertRaises(R.RecurrenceError):
            R.expand("daily", None)


class DescribeTests(unittest.TestCase):
    def test_readable_descriptions(self):
        cases = {
            "daily": "Every day",
            "RRULE:FREQ=DAILY;INTERVAL=3": "Every 3 days",
            "RRULE:FREQ=WEEKLY;BYDAY=MO,WE": "Every week on Monday, Wednesday",
            "RRULE:FREQ=MONTHLY;BYDAY=1MO": "Every month on 1st Monday",
            "RRULE:FREQ=MONTHLY;BYDAY=-1FR": "Every month on last Friday",
            "RRULE:FREQ=DAILY;COUNT=4": "Every day, 4 times",
        }
        for text, expected in cases.items():
            self.assertEqual(expected, R.describe(text), text)

    def test_until_is_mentioned(self):
        self.assertIn("until 2026-07-25", R.describe("RRULE:FREQ=DAILY;UNTIL=20260725"))


class ItemIntegrationTests(unittest.TestCase):
    def _item(self, line):
        return parse_text(line + "\n")[0][0]

    def test_rule_for_item_reads_sibling_details(self):
        item = self._item("[ ] T A repeat:weekly interval:2 count:5 until:2027-01-01")

        rule = R.rule_for_item(item)

        self.assertEqual(2, rule["interval"])
        self.assertEqual(5, rule["count"])
        self.assertEqual(date(2027, 1, 1), rule["until"].date())

    def test_rule_for_item_without_repeat(self):
        self.assertIsNone(R.rule_for_item(self._item("[ ] T A due:2026-07-20")))

    def test_complete_materializes_byday_occurrences(self):
        item = self._item('[ ] T A due:2026-07-20 repeat:"RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"')

        _key, nxt, _rule = next_repeat_occurrence(item, "due", date(2026, 7, 20))

        self.assertEqual(date(2026, 7, 22), nxt.date())

    def test_complete_materializes_positional_byday(self):
        item = self._item('[ ] T A due:2026-08-03 repeat:"RRULE:FREQ=MONTHLY;BYDAY=1MO"')

        _key, nxt, _rule = next_repeat_occurrence(item, "due", date(2026, 8, 3))

        self.assertEqual(date(2026, 9, 7), nxt.date())
        self.assertEqual(0, nxt.weekday())

    def test_complete_materializes_end_of_month(self):
        item = self._item('[ ] T A due:2026-07-31 repeat:"RRULE:FREQ=MONTHLY;BYMONTHDAY=-1"')

        _key, nxt, _rule = next_repeat_occurrence(item, "due", date(2026, 7, 31))

        self.assertEqual(date(2026, 8, 31), nxt.date())

    def test_simple_rules_keep_their_arithmetic(self):
        item = self._item("[ ] T A due:2026-07-20 repeat:weekly")

        _key, nxt, _rule = next_repeat_occurrence(item, "due", date(2026, 7, 20))

        self.assertEqual(date(2026, 7, 27), nxt.date())

    def test_until_stops_materialization(self):
        item = self._item('[ ] T A due:2026-07-20 repeat:"RRULE:FREQ=WEEKLY;UNTIL=20260722"')

        _key, nxt, _rule = next_repeat_occurrence(item, "due", date(2026, 7, 20))

        self.assertIsNone(nxt)

    def test_agenda_expands_positional_byday(self):
        items = parse_text(
            "[ ] E Board id:e1 from:2026-08-03T10:00 repeat:RRULE:FREQ=MONTHLY;BYDAY=1MO\n"
        )[0]

        matches = item_time_matches(items[0], datetime(2026, 8, 1), datetime(2026, 11, 30))

        self.assertEqual(
            ["2026-08-03", "2026-09-07", "2026-10-05", "2026-11-02"],
            [match["start"][:10] for match in matches],
        )

    def test_agenda_expands_bymonthday(self):
        items = parse_text(
            "[ ] E Payday id:e2 from:2026-08-31T09:00 repeat:RRULE:FREQ=MONTHLY;BYMONTHDAY=-1\n"
        )[0]

        matches = item_time_matches(items[0], datetime(2026, 8, 1), datetime(2026, 11, 1))

        self.assertEqual(["2026-08-31", "2026-09-30", "2026-10-31"], [m["start"][:10] for m in matches])

    def test_agenda_still_handles_plain_rules(self):
        items = parse_text("[ ] E Weekly id:e0 from:2026-08-03T09:00 repeat:weekly\n")[0]

        matches = item_time_matches(items[0], datetime(2026, 8, 1), datetime(2026, 9, 1))

        self.assertEqual(["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31"],
                         [m["start"][:10] for m in matches])

    def test_agenda_records_still_build(self):
        items = parse_text(
            "[ ] E Board id:e1 from:2026-08-03T10:00 repeat:RRULE:FREQ=MONTHLY;BYDAY=1MO\n"
        )[0]

        records = agenda_records(items, datetime(2026, 8, 1), datetime(2026, 11, 30))

        self.assertEqual(1, len(records))
        self.assertTrue(records[0]["generated"])


def _run_cli(cwd, *args):
    env = dict(os.environ, PYTHONPATH=ROOT_DIR, PYTHONIOENCODING="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "lifetxt"] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env,
    )
    out, _err = process.communicate()
    return out.decode("utf-8", "replace").strip(), process.returncode


class RruleCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Board id:t1 due:2026-08-03 repeat:RRULE:FREQ=MONTHLY;BYDAY=1MO\n"
                "[ ] T Plain id:t2 due:2026-07-20 repeat:weekly\n"
                "[ ] T NoRepeat id:t3 due:2026-07-20\n"
            )

    def test_expands_a_rule_given_on_the_command_line(self):
        out, code = _run_cli(
            self.tmp.name, "rrule", "RRULE:FREQ=WEEKLY;BYDAY=MO,WE", "--from", "2026-07-20", "--count", "3"
        )

        self.assertEqual(0, code, out)
        self.assertIn("Every week on Monday, Wednesday", out)
        self.assertIn("2026-07-20", out)
        self.assertIn("2026-07-22", out)

    def test_expands_an_items_repeat(self):
        out, code = _run_cli(self.tmp.name, "rrule", "--path", "life.txt", "--id", "t1", "--count", "2")

        self.assertEqual(0, code, out)
        self.assertIn("2026-08-03", out)
        self.assertIn("2026-09-07", out)

    def test_json_output_shape(self):
        import json

        out, code = _run_cli(
            self.tmp.name, "rrule", "RRULE:FREQ=DAILY;COUNT=2", "--from", "2026-07-20", "--format", "json"
        )

        payload = json.loads(out)
        self.assertEqual("daily", payload["frequency"])
        self.assertEqual(2, len(payload["occurrences"]))
        self.assertEqual([], payload["unsupported"])

    def test_life_output_is_valid(self):
        out, code = _run_cli(
            self.tmp.name, "rrule", "--path", "life.txt", "--id", "t2", "--count", "2", "--format", "life"
        )

        self.assertEqual(0, code, out)
        _items, diagnostics = parse_text(out + "\n")
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])

    def test_window_options(self):
        out, code = _run_cli(
            self.tmp.name, "rrule", "daily", "--from", "2026-07-20",
            "--after", "2026-07-23", "--before", "2026-07-25",
        )

        self.assertEqual(0, code, out)
        self.assertIn("2026-07-23", out)
        self.assertNotIn("2026-07-20 ", out)

    def test_errors_are_reported(self):
        for args, expected in (
            (["rrule", "RRULE:FREQ=HOURLY"], "FREQ"),
            (["rrule"], "Pass a rule"),
            (["rrule", "--path", "life.txt", "--id", "nope"], "No item"),
            (["rrule", "--path", "life.txt", "--id", "t3"], "no repeat:"),
            (["rrule", "--id", "t1"], "--path"),
        ):
            out, code = _run_cli(self.tmp.name, *args)

            self.assertNotEqual(0, code, " ".join(args))
            self.assertIn(expected, out, " ".join(args))

    def test_unsupported_parts_are_warned_about(self):
        out, code = _run_cli(
            self.tmp.name, "rrule", "RRULE:FREQ=WEEKLY;BYDAY=MO;BYSETPOS=1", "--from", "2026-07-20"
        )

        self.assertEqual(0, code)
        self.assertIn("BYSETPOS", out)


if __name__ == "__main__":
    unittest.main()
