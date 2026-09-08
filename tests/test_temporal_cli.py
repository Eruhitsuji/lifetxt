"""CLI wiring tests for `lifetxt temporal` (#481/#485)."""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] T Ship_report due:2000-01-01 id:t1\n"
    "[ ] T Review_draft due:2000-01-02 id:t2\n"
)

THREAD_SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] E Plan id:plan on:2000-01-01\n"
    "[x] E Actual id:actual on:2000-01-01 realizes:plan\n"
    "[ ] E Next id:next on:2000-02-01 follows:actual\n"
)


class TemporalCliTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=SAMPLE):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_temporal_text_output_shows_facts_and_related_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "t1", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Temporal context for t1", stdout)
            self.assertIn("overdue_by", stdout)
            self.assertIn("t2", stdout)
            self.assertIn("Review_draft", stdout)

    def test_temporal_json_output_matches_the_canonical_schema_marker(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "t1", src, "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("temporal-context-v1", data["schema"])
            self.assertEqual("t1", data["target_id"])
            self.assertEqual(["t2"], [edge["target_id"] for edge in data["related"]])

    def test_temporal_unknown_id_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("temporal", "nope", src)
            self.assertNotEqual(0, code)
            self.assertIn("No item with id", stderr)

    def test_temporal_window_and_limit_flags_are_honoured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "temporal", "t1", src, "--window", "0", "--json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            # t2 is one day away; a zero-day window excludes it.
            self.assertEqual([], data["related"])

    def test_thread_json_exposes_the_shared_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("thread", "actual", src, "--json")
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual("temporal-thread-v1", data["schema"])
            self.assertEqual(
                ["plan"], [r["id"] for r in data["relations"]["realized_plans"]]
            )
            self.assertEqual(
                ["next"], [r["id"] for r in data["relations"]["successors"]]
            )

    def test_thread_human_output_names_lifecycle_groups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir, THREAD_SAMPLE)
            stdout, stderr, code = run_cli("thread", "actual", src)
            self.assertEqual(0, code, stderr)
            self.assertIn("Temporal thread for actual", stdout)
            self.assertIn("Realized plans", stdout)
            self.assertIn("Successors", stdout)


if __name__ == "__main__":
    unittest.main()
