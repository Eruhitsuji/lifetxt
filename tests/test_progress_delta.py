import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt.progress_delta import format_progress_delta, progress_delta
from lifetxt.progress_history import build_progress_event
from lifetxt.serializer import item_to_line


REVISION = "a" * 64
UTC = datetime.timezone.utc


def _event(before, after, sequence, at, operation="set"):
    return item_to_line(
        build_progress_event(
            "task-1",
            before,
            after,
            operation,
            at,
            sequence,
            "PTX-task-1-%06d" % sequence,
            REVISION,
        )
    )


def _items(current, *events):
    text = "[ ] T Task id:task-1 progress:%s\n%s\n" % (
        current,
        "\n".join(events),
    )
    items, diagnostics = parse_text(text)
    assert not [row for row in diagnostics if row.severity == "error"]
    return items


def _at(day, hour=0):
    return datetime.datetime(2026, 9, day, hour, tzinfo=UTC)


class ProgressDeltaTests(unittest.TestCase):
    def test_percentage_delta_uses_percentage_points(self):
        items = _items(
            "40%",
            _event("20%", "25%", 1, "2026-09-01T00:00:00Z"),
            _event("25%", "40%", 2, "2026-09-08T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertTrue(result["available"])
        self.assertEqual("25%", result["start_raw"])
        self.assertEqual("40%", result["end_raw"])
        self.assertEqual(0.15, result["delta_ratio"])
        self.assertEqual(15.0, result["delta_percentage_points"])

    def test_negative_delta_is_not_clamped(self):
        items = _items(
            "55%",
            _event("60%", "70%", 1, "2026-09-01T00:00:00Z"),
            _event("70%", "55%", 2, "2026-09-08T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertAlmostEqual(-15.0, result["delta_percentage_points"])
        self.assertIn("delta: -15 pp", format_progress_delta(result))

    def test_fraction_and_denominator_change_use_normalized_ratio(self):
        items = _items(
            "12/20",
            _event("2/10", "3/10", 1, "2026-09-01T00:00:00Z"),
            _event("3/10", "12/20", 2, "2026-09-08T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertAlmostEqual(30.0, result["delta_percentage_points"])

    def test_equivalent_fraction_after_denominator_change_is_zero(self):
        items = _items(
            "6/20",
            _event("2/10", "3/10", 1, "2026-09-01T00:00:00Z"),
            _event("3/10", "6/20", 2, "2026-09-08T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertEqual(0.0, result["delta_ratio"])
        self.assertEqual(0.0, result["delta_percentage_points"])
        self.assertIn("delta: +0 pp", format_progress_delta(result))

    def test_mixed_percentage_and_fraction_are_comparable(self):
        items = _items(
            "3/4",
            _event("10%", "25%", 1, "2026-09-01T00:00:00Z"),
            _event("25%", "3/4", 2, "2026-09-08T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertAlmostEqual(50.0, result["delta_percentage_points"])

    def test_event_after_end_is_not_used(self):
        items = _items(
            "50%",
            _event("10%", "25%", 1, "2026-09-01T00:00:00Z"),
            _event("25%", "40%", 2, "2026-09-08T00:00:00Z"),
            _event("40%", "50%", 3, "2026-09-09T00:00:00Z"),
        )
        result = progress_delta(items, "task-1", _at(1), _at(8, 23))
        self.assertEqual("40%", result["end_raw"])

    def test_missing_start_baseline_is_unavailable_not_zero(self):
        items = _items(
            "40%", _event("25%", "40%", 1, "2026-09-05T00:00:00Z")
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertFalse(result["available"])
        self.assertEqual("start_unavailable", result["reason"])
        self.assertEqual("40%", result["end_raw"])
        self.assertIsNone(result["delta_ratio"])
        self.assertIn("end:   40%", format_progress_delta(result))

    def test_no_history_is_unavailable(self):
        result = progress_delta(_items("40%"), "task-1", _at(1), _at(8))
        self.assertFalse(result["available"])
        self.assertEqual("no_history", result["reason"])

    def test_incomplete_history_is_unavailable(self):
        items = _items(
            "50%", _event("25%", "40%", 1, "2026-09-01T00:00:00Z")
        )
        result = progress_delta(items, "task-1", _at(1), _at(8))
        self.assertFalse(result["available"])
        self.assertEqual("history_incomplete", result["reason"])

    def test_naive_or_reversed_boundaries_are_rejected(self):
        items = _items("40%")
        with self.assertRaises(ValueError):
            progress_delta(items, "task-1", datetime.datetime(2026, 9, 1), _at(8))
        with self.assertRaises(ValueError):
            progress_delta(items, "task-1", _at(8), _at(1))


class ProgressDeltaCliTests(unittest.TestCase):
    def _run(self, path, output_format="text"):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "lifetxt",
                "stats",
                path,
                "--progress-delta",
                "task",
                "--from",
                "2026-09-01",
                "--to",
                "2026-09-08",
                "--format",
                output_format,
            ],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def _fixture(self, directory):
        path = os.path.join(directory, "life.txt")
        text = "\n".join(
            [
                "#! timezone:UTC",
                "[ ] T Task id:task-1 progress:40%",
                _event("20%", "25%", 1, "2026-09-01T00:00:00Z"),
                _event("25%", "40%", 2, "2026-09-08T00:00:00Z"),
                "",
            ]
        )
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_text_and_json_use_the_same_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._fixture(directory)
            text_result = self._run(path)
            json_result = self._run(path, "json")
        self.assertEqual(0, text_result.returncode, text_result.stderr)
        self.assertEqual(0, json_result.returncode, json_result.stderr)
        self.assertIn("start: 25%", text_result.stdout)
        self.assertIn("delta: +15 pp", text_result.stdout)
        data = json.loads(json_result.stdout)
        self.assertEqual("lifetxt-progress-delta-v1", data["schema"])
        self.assertEqual("25%", data["start_raw"])
        self.assertAlmostEqual(15.0, data["delta_percentage_points"])
        schema_path = os.path.join(
            os.getcwd(), "dist", "schemas", "progress-delta-v1.schema.json"
        )
        with open(schema_path, encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(set(schema["required"]), set(data))
        self.assertFalse(schema["additionalProperties"])
