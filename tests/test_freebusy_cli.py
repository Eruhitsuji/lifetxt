"""CLI wiring tests for `lifetxt freebusy` (#673)."""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] E Standup from:2026-08-22T10:00 to:2026-08-22T11:00 id:e1\n"
    "[ ] E Review from:2026-08-22T10:30 to:2026-08-22T11:30 id:e2\n"
    "[ ] R Ping at:2026-08-22T09:00 id:r1\n"
    "[ ] T NotBusy due:2026-08-22 id:t1\n"
)


class FreebusyCliTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=SAMPLE):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_text_output_shows_busy_free_conflicts_and_instants(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T09:00",
                "--to",
                "2026-08-22T18:00",
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Busy (2):", stdout)
            self.assertIn("Standup", stdout)
            self.assertIn("Conflicts (1):", stdout)
            self.assertIn("Standup overlaps Review", stdout)
            self.assertIn("Instants (1):", stdout)
            self.assertIn("Ping", stdout)

    def test_json_output_matches_the_canonical_schema_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T09:00",
                "--to",
                "2026-08-22T18:00",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("freebusy-v1", data["schema"])
            self.assertEqual(2, len(data["busy"]))
            self.assertEqual(1, len(data["conflicts"]))

    def test_day_start_and_day_end_must_be_used_together(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T09:00",
                "--to",
                "2026-08-22T18:00",
                "--day-start",
                "09:00",
            )
            self.assertNotEqual(0, code)
            self.assertIn("--day-start and --day-end must be used together", stderr)

    def test_day_window_clips_free_intervals_in_json_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T00:00",
                "--to",
                "2026-08-23T00:00",
                "--day-start",
                "09:00",
                "--day-end",
                "17:00",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            for entry in data["free"]:
                self.assertGreaterEqual(entry["start"][11:16], "09:00")
                self.assertLessEqual(entry["end"][11:16], "17:00")

    def test_invalid_day_start_end_ordering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T09:00",
                "--to",
                "2026-08-22T18:00",
                "--day-start",
                "17:00",
                "--day-end",
                "09:00",
            )
            self.assertNotEqual(0, code)
            self.assertIn("--day-end must be later than --day-start", stderr)

    def test_range_end_before_start_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T18:00",
                "--to",
                "2026-08-22T09:00",
            )
            self.assertNotEqual(0, code)

    def test_diagnostics_are_shown_as_notes_in_text_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir, "[ ] E Bad from:not-a-date id:e1\n[ ] E Untimed id:e2\n"
            )
            stdout, stderr, code = run_cli(
                "freebusy",
                src,
                "--from",
                "2026-08-22T00:00",
                "--to",
                "2026-08-23T00:00",
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("NOTE: invalid_time_value", stdout)
            self.assertIn("NOTE: missing_time_detail", stdout)

    def test_help_documents_the_command(self):
        stdout, stderr, code = run_cli("freebusy", "--help")
        self.assertEqual(0, code, stderr)
        self.assertIn("--day-start", stdout)
        self.assertIn("--day-end", stdout)


if __name__ == "__main__":
    unittest.main()
