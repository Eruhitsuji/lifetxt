"""Integration tests for `progress:` validation via `lifetxt check` (#646):
valid percentage/fraction values produce no diagnostic, invalid values
produce W230 with an actionable message and hint, status and progress
stay independent (no auto-sync), and the raw representation survives a
parse/serialize roundtrip unchanged.
"""

import os
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line
from tests.test_lifetxt import normalize_newlines, run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class ValidProgressTests(unittest.TestCase):
    def test_valid_percentage_and_fraction_produce_no_diagnostic(self):
        path = _make_file(
            '[/] T "Write paper" progress:75%\n[/] T "Experiment" progress:3/10\n'
        )
        try:
            out, err, rc = run_cli("check", path)
            self.assertEqual(0, rc)
            self.assertNotIn("W230", out)
        finally:
            os.unlink(path)


class InvalidProgressTests(unittest.TestCase):
    def test_out_of_range_percentage_is_flagged(self):
        path = _make_file('[/] T "Bad" progress:120%\n')
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn("W230", out)
            self.assertIn("out of range", out)
            self.assertIn("Use progress:75% or progress:3/5.", out)
        finally:
            os.unlink(path)

    def test_zero_denominator_fraction_is_flagged(self):
        path = _make_file('[/] T "Bad" progress:5/0\n')
        try:
            out, err, rc = run_cli("check", path)
            self.assertIn("W230", out)
        finally:
            os.unlink(path)

    def test_fraction_exceeding_total_is_flagged(self):
        path = _make_file('[/] T "Bad" progress:12/10\n')
        try:
            out, err, rc = run_cli("check", path)
            self.assertIn("W230", out)
        finally:
            os.unlink(path)

    def test_bare_unitless_number_is_flagged(self):
        path = _make_file('[/] T "Bad" progress:0.5\n')
        try:
            out, err, rc = run_cli("check", path)
            self.assertIn("W230", out)
        finally:
            os.unlink(path)


class StatusProgressIndependenceTests(unittest.TestCase):
    def test_100_percent_progress_does_not_force_done_status(self):
        path = _make_file('[ ] T "Review pending" progress:100%\n')
        try:
            out, err, rc = run_cli("check", path)
            self.assertEqual(0, rc)
            self.assertNotIn("W230", out)
        finally:
            os.unlink(path)

    def test_done_status_does_not_require_100_percent_progress(self):
        path = _make_file('[x] T "Cut short" progress:60% done:2026-01-01\n')
        try:
            out, err, rc = run_cli("check", path)
            self.assertEqual(0, rc)
            self.assertNotIn("W230", out)
        finally:
            os.unlink(path)


class RoundtripPreservationTests(unittest.TestCase):
    def test_fraction_representation_survives_reparse_unchanged(self):
        text = '[/] T "Experiment" progress:3/10\n'
        items, diagnostics = parse_text(text)
        self.assertEqual([], [d for d in diagnostics if d.code == "W230"])
        serialized = item_to_line(items[0])
        self.assertIn("progress:3/10", serialized)
        self.assertNotIn("progress:30%", serialized)

    def test_percentage_representation_survives_reparse_unchanged(self):
        text = '[/] T "Write paper" progress:75%\n'
        items, diagnostics = parse_text(text)
        serialized = item_to_line(items[0])
        self.assertIn("progress:75%", serialized)


if __name__ == "__main__":
    unittest.main()
