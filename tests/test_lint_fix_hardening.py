"""Tests for guarded `lint --fix` hardening (#635): a complete fix plan is
built and validated with the canonical parser before any single write, no
file is partially fixed on validation failure, ambiguous findings (L003
duplicate keys, L100 custom-rule matches) are never auto-applied, and
`--dry-run` previews without mutating anything.
"""

import os
import tempfile
import unittest

from tests.test_lifetxt import run_cli


def _make_file(text):
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    handle.write(text)
    handle.flush()
    handle.close()
    return handle.name


class LintFixSafeScopeTests(unittest.TestCase):
    def test_duplicate_key_and_custom_rule_codes_are_never_classified_fixable(self):
        from lifetxt.cli import _LINT_FIXABLE_CODES

        self.assertEqual({"L001", "L002"}, set(_LINT_FIXABLE_CODES))
        self.assertNotIn("L003", _LINT_FIXABLE_CODES)
        self.assertNotIn("L100", _LINT_FIXABLE_CODES)

    def test_custom_ruleset_match_is_never_auto_applied(self):
        path = _make_file("[ ] T Task  weird_key:value\n")
        ruleset_path = _make_file(
            '[{"pattern": "weird_key", "replacement": "priority", '
            '"message": "custom rule for {key}"}]\n'
        )
        try:
            before = open(path, encoding="utf-8").read()
            out, err, rc = run_cli("lint", path, "--ruleset", ruleset_path, "--fix")
            after = open(path, encoding="utf-8").read()
            self.assertEqual(before, after)
            self.assertIn("no unique safe fix", out)
        finally:
            os.unlink(path)
            os.unlink(ruleset_path)

    def test_only_typo_and_casing_findings_are_applied(self):
        path = _make_file("[ ] T Task  proj:work  tag:a  tag:b\n")
        try:
            out, err, rc = run_cli("lint", path, "--fix")
            content = open(path, encoding="utf-8").read()
            self.assertIn("project:work", content)
            # The duplicate tag: finding stays untouched.
            self.assertIn("tag:a", content)
            self.assertIn("tag:b", content)
        finally:
            os.unlink(path)


class LintFixDryRunTests(unittest.TestCase):
    def test_dry_run_previews_without_writing(self):
        path = _make_file("[ ] T Task  proj:work\n")
        try:
            before = open(path, encoding="utf-8").read()
            out, err, rc = run_cli("lint", path, "--fix", "--dry-run")
            after = open(path, encoding="utf-8").read()
            self.assertEqual(before, after)
            self.assertIn("[dry-run]", out)
        finally:
            os.unlink(path)

    def test_dry_run_reports_the_same_fixable_count_as_a_real_fix(self):
        path = _make_file("[ ] T Task  proj:work\n[ ] T Another  prio:high\n")
        try:
            out_dry, _, _ = run_cli("lint", path, "--fix", "--dry-run")
            self.assertIn("Would fix 2 issue(s)", out_dry)
        finally:
            os.unlink(path)


class LintFixIdempotencyTests(unittest.TestCase):
    def test_fixed_file_reports_no_more_fixable_findings_on_rerun(self):
        path = _make_file("[ ] T Task  proj:work\n")
        try:
            run_cli("lint", path, "--fix")
            out, err, rc = run_cli("lint", path)
            self.assertEqual(rc, 0)
            self.assertIn("No lint issues", out)
        finally:
            os.unlink(path)


class LintFixNoPartialWriteTests(unittest.TestCase):
    def test_multi_file_fix_applies_independently_per_file(self):
        path_a = _make_file("[ ] T Task  proj:work\n")
        path_b = _make_file("[ ] T Task  prio:high\n")
        try:
            out, err, rc = run_cli("lint", path_a, path_b, "--fix")
            content_a = open(path_a, encoding="utf-8").read()
            content_b = open(path_b, encoding="utf-8").read()
            self.assertIn("project:work", content_a)
            self.assertIn("priority:high", content_b)
        finally:
            os.unlink(path_a)
            os.unlink(path_b)


if __name__ == "__main__":
    unittest.main()
