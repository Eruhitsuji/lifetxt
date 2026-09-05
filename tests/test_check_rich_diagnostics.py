"""Integration tests for `lifetxt check`'s rich diagnostic rendering (#639).

Covers the CLI wiring of `lifetxt/diagnostic_render.py` into
`command_check()`'s text output branch: source snippet display, hint
display, a trailing multi-diagnostic summary line, `--format json`
invariance, and regression coverage for the pre-existing W225 guidance,
filtering, and exit-code behavior.
"""

import json
import os
import tempfile
import unittest

from tests.test_lifetxt import normalize_newlines, run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class CheckRichRenderingTests(unittest.TestCase):
    def test_source_snippet_and_caret_shown_for_a_real_diagnostic(self):
        path = _make_file("[ ] T First id:task_001\n[ ] T Second id:task_001\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("WARNING W213", out)
            self.assertIn("2 | [ ] T Second id:task_001", out)
        finally:
            os.unlink(path)

    def test_trailing_summary_line_reflects_error_and_warning_counts(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("1 problem: 0 errors, 1 warning", out)
        finally:
            os.unlink(path)

    def test_unicode_source_lines_render_without_crashing(self):
        path = _make_file("[ ] T 日本語タスク id:dup\n[ ] T Other id:dup\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("2 | [ ] T Other id:dup", out)
        finally:
            os.unlink(path)

    def test_long_source_line_is_rendered_in_full(self):
        long_title = "x" * 250
        path = _make_file("[ ] T First id:dup\n[ ] T %s id:dup\n" % long_title)
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn(long_title, out)
        finally:
            os.unlink(path)

    def test_w225_guidance_and_hint_both_present(self):
        path = _make_file(
            "[x] T Parent_task id:P001\n[ ] T Child_task parent:P001 id:C001\n"
        )
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn("W225", out)
            self.assertIn("Hint", out)
            self.assertIn("adopt", out)
        finally:
            os.unlink(path)

    def test_format_json_is_unaffected_by_rich_rendering(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "json")
            payload = json.loads(out)
            self.assertEqual(1, len(payload))
            self.assertEqual("W213", payload[0]["code"])
            self.assertNotIn("^", json.dumps(payload))
        finally:
            os.unlink(path)

    def test_filter_by_code_still_works(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--code", "W213")
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertIn("WARNING W213", out)
        finally:
            os.unlink(path)

    def test_ignore_removes_diagnostic_from_rich_output(self):
        path = _make_file("[ ] T First id:dup\n[ ] T Second id:dup\n")
        try:
            out, err, rc = run_cli("check", path, "--ignore", "W213")
            out = normalize_newlines(out)
            self.assertEqual(rc, 0)
            self.assertNotIn("W213", out)
        finally:
            os.unlink(path)

    def test_ok_no_diagnostics_output_is_unchanged(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path)
            self.assertEqual(rc, 0)
            self.assertIn("OK: 1 item(s)", out)
            self.assertNotIn("problem", out)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
