"""Diagnostics and concrete agenda behavior for supported and invalid RRULEs."""

import json
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path

from lifetxt.agenda import item_time_matches, next_repeat_occurrence
from lifetxt.parser import parse_text


ROOT = Path(__file__).resolve().parents[1]
START = datetime(2030, 10, 14)
END = datetime(2030, 11, 16)


def record(rule, extra=""):
    return '[ ] E Example on:2030-10-14 repeat:"RRULE:FREQ=%s" %s' % (rule, extra)


class RruleDiagnosticTests(unittest.TestCase):
    def test_invalid_supported_values_warn_and_keep_only_authored_anchor(self):
        for suffix in (
            "WEEKLY;WKST=XX",
            "MONTHLY;BYMONTHDAY=32",
            "MONTHLY;BYMONTH=13",
            "WEEKLY;BYDAY=MO;BYMONTHDAY=1",
            "WEEKLY;BYDAY=2MO",
            "MONTHLY;BYDAY=0MO",
            "MONTHLY;BYDAY=MO,",
            "MONTHLY;BYMONTH=",
            "MONTHLY;COUNT=0",
            "MONTHLY;UNTIL=oops",
            "MONTHLY;JUNK",
            "MONTHLY;BYDAY=2MO;BYHOUR=9",
            "HOURLY",
        ):
            with self.subTest(suffix=suffix):
                items, diagnostics = parse_text(record(suffix))
                self.assertTrue(any(d.code == "W223" for d in diagnostics))
                matches = item_time_matches(items[0], START, END)
                self.assertEqual(1, len(matches))
                self.assertEqual("on", matches[0]["key"])
                self.assertNotIn("repeat", matches[0])
                self.assertEqual(
                    [], item_time_matches(items[0], datetime(2030, 10, 15), END)
                )

    def test_plain_monthly_and_yearly_weekdays_expand(self):
        for rule in ("MONTHLY;BYDAY=MO", "YEARLY;BYMONTH=10,11;BYDAY=MO"):
            with self.subTest(rule=rule):
                items, diagnostics = parse_text(record(rule))
                self.assertFalse(any(d.code == "W223" for d in diagnostics))
                matches = item_time_matches(items[0], START, END)
                self.assertEqual(
                    [
                        "2030-10-14",
                        "2030-10-21",
                        "2030-10-28",
                        "2030-11-04",
                        "2030-11-11",
                    ],
                    [m["start"][:10] for m in matches],
                )

    def test_weekdays_short_name_still_expands(self):
        item = parse_text("[ ] E A on:2030-10-14 repeat:weekdays")[0][0]
        matches = item_time_matches(item, START, datetime(2030, 10, 19))
        self.assertEqual(
            ["2030-10-14", "2030-10-15", "2030-10-16", "2030-10-17", "2030-10-18"],
            [m["start"][:10] for m in matches],
        )

    def test_empty_valid_filters_never_fall_back_to_anchor(self):
        for rule in ("MONTHLY;BYDAY=6MO", "MONTHLY;BYMONTHDAY=31;BYDAY=2MO"):
            with self.subTest(rule=rule):
                items, diagnostics = parse_text(record(rule))
                self.assertFalse(any(d.code == "W223" for d in diagnostics))
                self.assertEqual([], item_time_matches(items[0], START, END))

    def test_valid_values_and_unknown_custom_fields_still_parse(self):
        items, diagnostics = parse_text(
            record("MONTHLY;BYMONTHDAY=-1", "custom_x:keep")
        )
        self.assertEqual(["keep"], items[0].details["custom_x"])
        self.assertFalse(
            any(d.severity == "error" or d.code == "W223" for d in diagnostics)
        )
        matches = item_time_matches(items[0], START, END)
        self.assertEqual(["2030-10-31"], [m["start"][:10] for m in matches])

    def test_complete_uses_plain_monthly_byday_and_refuses_invalid_rules(self):
        item = parse_text(
            '[ ] T A due:2030-10-14 repeat:"RRULE:FREQ=MONTHLY;BYDAY=MO"'
        )[0][0]
        self.assertEqual(
            datetime(2030, 10, 21), next_repeat_occurrence(item, "due", START.date())[1]
        )
        bad = parse_text(
            '[ ] T A due:2030-10-14 repeat:"RRULE:FREQ=MONTHLY;BYMONTHDAY=32"'
        )[0][0]
        with self.assertRaises(ValueError):
            next_repeat_occurrence(bad, "due", START.date())

    def test_check_warning_exit_policy_and_agenda_cli(self):
        source = record("MONTHLY;BYMONTHDAY=32") + "\n"
        for flags, expected in (([], 0), (["--warnings-as-errors"], 1)):
            with self.subTest(flags=flags):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "lifetxt",
                        "check",
                        "--format",
                        "json",
                        *flags,
                        "-",
                    ],
                    input=source,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(expected, result.returncode, result.stderr)
                self.assertIn("W223", [d["code"] for d in json.loads(result.stdout)])
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "agenda",
                "--from",
                "2030-10-14",
                "--to",
                "2030-11-15",
                "--format",
                "json",
                "-",
            ],
            input=source,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual(1, len(rows))
        self.assertFalse(rows[0].get("generated", False))
        self.assertIn("W223", result.stderr)
