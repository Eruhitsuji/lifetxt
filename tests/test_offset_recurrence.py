"""Authored offset instants survive agenda anchors and recurrence expansion."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

from lifetxt.agenda import item_time_matches
from lifetxt.parser import parse_text
from lifetxt.recurrence import expand
from lifetxt.timezone_policy import timezone_context


class OffsetRecurrenceTests(unittest.TestCase):
    def matches(self, line, start, end):
        items, diagnostics = parse_text(line)
        self.assertFalse(diagnostics)
        with timezone_context("UTC"):
            return item_time_matches(
                items[0], datetime.fromisoformat(start), datetime.fromisoformat(end)
            )

    def test_split_and_full_anchors_preserve_same_instant(self):
        for clock in ("07:00+09:00", "23:00-09:00", "07:00:12.25+05:45", "07:00Z"):
            for suffix in (
                "",
                " repeat:daily count:2",
                " repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=2",
            ):
                with self.subTest(clock=clock, repeat=suffix):
                    split = self.matches(
                        "[ ] E Split on:2030-10-14 at:" + clock + suffix,
                        "2030-10-13",
                        "2030-10-18",
                    )
                    full = self.matches(
                        "[ ] E Full at:2030-10-14T" + clock + suffix,
                        "2030-10-13",
                        "2030-10-18",
                    )
                    split = [m["start"] for m in split if m["key"] != "on"]
                    full = [m["start"] for m in full]
                    self.assertEqual(full, split)
                    self.assertTrue(
                        all(datetime.fromisoformat(v).tzinfo is not None for v in split)
                    )

    def test_aware_candidates_all_frequencies(self):
        start = datetime.fromisoformat("2030-10-14T07:00:12.25+09:00")
        for rule in (
            "FREQ=DAILY",
            "FREQ=WEEKLY;BYDAY=MO,WE",
            "FREQ=MONTHLY;BYDAY=2MO",
            "FREQ=YEARLY;BYMONTH=10;BYDAY=2MO",
        ):
            with self.subTest(rule=rule), timezone_context("UTC"):
                result = expand("RRULE:" + rule + ";COUNT=2", start)
                self.assertEqual(2, len(result))
                self.assertTrue(all(v.utcoffset() == start.utcoffset() for v in result))
                self.assertTrue(all(v.timetz() == start.timetz() for v in result))

    def test_configured_window_half_open_and_count(self):
        for repeat in ("daily", "RRULE:FREQ=WEEKLY;BYDAY=MO,WE"):
            line = "[ ] E Full at:2030-10-14T07:00+09:00 repeat:" + repeat + " count:2"
            matches = self.matches(
                line, "2030-10-13T22:00", "2030-10-13T22:00:00.000001"
            )
            self.assertEqual(1, len(matches))
            self.assertEqual(
                [], self.matches(line, "2030-10-13T21:59", "2030-10-13T22:00")
            )
            self.assertEqual([], self.matches(line, "2030-10-20", "2030-10-21"))

    def test_until_in_configured_zone(self):
        line = "[ ] E Full at:2030-10-14T07:00+09:00 repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;UNTIL=20301015"
        result = self.matches(line, "2030-10-13", "2030-10-18")
        self.assertEqual(2, len(result))  # Wednesday 07:00 +09 is Tuesday UTC.

    def test_floating_negative_offset_keeps_calendar_displacement(self):
        for suffix in ("", " repeat:daily"):
            with self.subTest(suffix=suffix):
                result = self.matches(
                    "[ ] E Floating at:23:00-09:00" + suffix, "2030-10-14", "2030-10-15"
                )
                self.assertEqual(
                    ["2030-10-13T23:00-09:00"], [m["start"] for m in result]
                )

    def test_configured_zone_and_mixed_interval_duration(self):
        items, diagnostics = parse_text(
            "[ ] E Span from:2030-10-14T07:00+09:00 to:2030-10-13T23:00 repeat:daily count:1"
        )
        self.assertFalse([d for d in diagnostics if d.severity == "error"])
        with timezone_context("UTC"):
            result = item_time_matches(
                items[0], datetime(2030, 10, 13, 22), datetime(2030, 10, 13, 23)
            )
        self.assertEqual("2030-10-14T08:00+09:00", result[0]["end"])
        with timezone_context("Asia/Tokyo"):
            items, _ = parse_text(
                "[ ] E Full at:2030-10-14T07:00+09:00 repeat:daily count:1"
            )
            result = item_time_matches(
                items[0], datetime(2030, 10, 14), datetime(2030, 10, 15)
            )
        self.assertEqual("2030-10-14T07:00+09:00", result[0]["start"])

    def test_naive_control(self):
        result = self.matches(
            "[ ] E Plain on:2030-10-14 at:07:00 repeat:daily count:2",
            "2030-10-13",
            "2030-10-18",
        )
        self.assertEqual(
            ["2030-10-14T07:00", "2030-10-15T07:00"], [m["start"] for m in result]
        )

    def test_cli_hosts_and_seasons_are_equivalent(self):
        root = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            (p / "config.json").write_text(
                '{"defaults":{"timezone":"UTC"}}', encoding="utf-8"
            )
            for day in ("2030-01-14", "2030-10-14"):
                (p / "life.txt").write_text(
                    "[ ] E Split on:"
                    + day
                    + " at:07:00+09:00 repeat:RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=2\n",
                    encoding="utf-8",
                )
                results = []
                for host in ("UTC", "Asia/Tokyo", "America/New_York"):
                    env = dict(
                        os.environ, TZ=host, LIFETXT_TIMEZONE="UTC", PYTHONPATH=root
                    )
                    proc = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "lifetxt",
                            "--config",
                            str(p / "config.json"),
                            "agenda",
                            str(p / "life.txt"),
                            "--from",
                            day + "T00:00",
                            "--to",
                            day + "T08:00",
                            "--format",
                            "json",
                        ],
                        env=env,
                        cwd=temp,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(0, proc.returncode, proc.stderr)
                    results.append(json.loads(proc.stdout))
                self.assertEqual(results[0], results[1])
                self.assertEqual(results[0], results[2])
                self.assertEqual([], results[0])  # Monday occurrence is Sunday UTC.


if __name__ == "__main__":
    unittest.main()
