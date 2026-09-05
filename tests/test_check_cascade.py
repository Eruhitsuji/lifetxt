"""Integration tests for `lifetxt check`'s cascade root-cause/secondary
notes (#642): a real E009/E010 cascade fixture, a real fixture where
independent diagnostics on one line must NOT be marked related, filtering
interaction (root filtered out, secondary filtered out), multi-file
sources, and `--format json` invariance.
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


class CheckCascadeIntegrationTests(unittest.TestCase):
    def test_unquoted_multiword_title_cascade_marks_root_and_secondaries(self):
        # A single unquoted, multi-word title spills into the detail
        # loop as several unrelated-looking E010s; all are consequences
        # of the same missing quotes.
        path = _make_file("[ ] T Write report due 2026-01-01\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn(
                "Related: 2 other diagnostic(s) on this line may be "
                "consequences of this one (see below).",
                out,
            )
            self.assertIn(
                "Related: possibly caused by E010 at column 13 above; fix that first.",
                out,
            )
        finally:
            os.unlink(path)

    def test_independent_same_line_diagnostics_are_never_marked_related(self):
        path = _make_file("[X]\tT Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path)
            out = normalize_newlines(out)
            self.assertIn("E001", out)
            self.assertIn("E003", out)
            self.assertIn("E008", out)
            self.assertNotIn("Related:", out)
        finally:
            os.unlink(path)

    def test_filtering_to_the_secondary_codes_only_still_groups_them(self):
        path = _make_file("[ ] T Title : value bad_token\n")
        try:
            out, err, rc = run_cli("check", path, "--code", "E010")
            out = normalize_newlines(out)
            self.assertNotIn("E009", out)
            self.assertIn(
                "Related: 1 other diagnostic(s) on this line may be "
                "consequences of this one (see below).",
                out,
            )
        finally:
            os.unlink(path)

    def test_filtering_to_a_lone_survivor_shows_no_relation_note(self):
        path = _make_file("[ ] T Title : value bad_token\n")
        try:
            out, err, rc = run_cli("check", path, "--code", "E009")
            out = normalize_newlines(out)
            self.assertIn("E009", out)
            self.assertNotIn("E010", out)
            self.assertNotIn("Related:", out)
        finally:
            os.unlink(path)

    def test_multi_file_sources_are_never_grouped_across_files(self):
        path_a = _make_file("[ ] T Write report due 2026-01-01\n")
        path_b = _make_file("[ ] T Write report due 2026-01-01\n")
        try:
            out, err, rc = run_cli("check", path_a, path_b)
            out = normalize_newlines(out)
            # Each file's own cascade is still detected...
            self.assertEqual(
                out.count(
                    "Related: 2 other diagnostic(s) on this line may be "
                    "consequences of this one (see below)."
                ),
                2,
            )
            # ...but no relation note ever crosses a source boundary: the
            # per-file group sizes must stay 3, not merge into one group
            # of 6 sharing the same line number.
            self.assertNotIn("Related: 5 other", out)
        finally:
            os.unlink(path_a)
            os.unlink(path_b)

    def test_format_json_is_completely_unaffected_by_cascade_grouping(self):
        path = _make_file("[ ] T Write report due 2026-01-01\n")
        try:
            out, err, rc = run_cli("check", path, "--format", "json")
            payload = json.loads(out)
            self.assertEqual(3, len(payload))
            self.assertNotIn("related", json.dumps(payload).lower())
            self.assertNotIn("cascade", json.dumps(payload).lower())
            self.assertNotIn("root", json.dumps(payload).lower())
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
