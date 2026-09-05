"""Japanese localization of beginner-facing diagnostics (#633): `check`,
`lint`, and `doctor`'s own fixed labels and next-step guidance.

Built on #631's shared locale resolver/catalog. Every test drives the real
installed entry point via `run_cli`; individual parser/validator diagnostic
hint text (hundreds of distinct English strings) is out of this bounded
slice's scope and stays English-only -- these tests cover the representative
surface documented in cli_taxonomy/cli.py's own catalog registration.
"""

import json
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


class CheckLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_ok_summary(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "check", path)
            self.assertEqual(rc, 0)
            self.assertIn("OK: 1 件", out)
        finally:
            os.unlink(path)

    def test_check_json_is_locale_invariant(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out_en, _, rc_en = run_cli("check", path, "--format", "json")
            out_ja, _, rc_ja = run_cli(
                "--lang", "ja", "check", path, "--format", "json"
            )
            self.assertEqual(rc_en, 0)
            self.assertEqual(rc_ja, 0)
            self.assertEqual(json.loads(out_en), json.loads(out_ja))
        finally:
            os.unlink(path)

    def test_english_default_check_is_unaffected(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("check", path)
            self.assertEqual(rc, 0)
            self.assertIn("OK: 1 item(s)", out)
        finally:
            os.unlink(path)


class LintLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_no_issues_message(self):
        path = _make_file("[ ] T Task  project:work  due:2026-01-01\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "lint", path)
            self.assertEqual(rc, 0)
            self.assertIn("見つかりませんでした", out)
        finally:
            os.unlink(path)

    def test_lang_ja_translates_typo_key_message(self):
        path = _make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "lint", path)
            self.assertNotEqual(rc, 0)
            self.assertIn("typo の可能性があります", out)
        finally:
            os.unlink(path)

    def test_lint_json_message_stays_english_regardless_of_locale(self):
        path = _make_file("[ ] T Task  proj:work\n")
        try:
            out_en, _, _ = run_cli("lint", path, "--format", "json")
            out_ja, _, _ = run_cli("--lang", "ja", "lint", path, "--format", "json")
            self.assertEqual(json.loads(out_en), json.loads(out_ja))
            self.assertIn("typo", json.loads(out_en)[0]["message"])
        finally:
            os.unlink(path)

    def test_lang_ja_translates_fix_summary(self):
        path = _make_file("[ ] T Task  proj:work\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "lint", path, "--fix")
            self.assertEqual(rc, 0)
            self.assertIn("修正しました", out)
        finally:
            os.unlink(path)


class DoctorLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_python_and_life_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            with open(life_file, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Buy_milk\n")
            out, err, rc = run_cli("--lang", "ja", "doctor", life_file)
            self.assertIn("見つかりました", out)

    def test_english_default_doctor_is_unaffected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            with open(life_file, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Buy_milk\n")
            out, err, rc = run_cli("doctor", life_file)
            self.assertIn("Found:", out)

    def test_doctor_json_is_locale_invariant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            with open(life_file, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Buy_milk\n")
            out_en, _, _ = run_cli("doctor", life_file, "--format", "json")
            out_ja, _, _ = run_cli(
                "--lang", "ja", "doctor", life_file, "--format", "json"
            )
            records_en = json.loads(out_en)
            records_ja = json.loads(out_ja)
            # The "disk" check embeds a live free-space reading in its message
            # (part of cap-doctor-unification's system diagnostics). The two
            # subprocess calls above are genuinely separate, moments apart, so
            # real disk activity on the host between them can change that one
            # number even though every other field is correctly
            # locale-invariant (#662). Compare everything except that live
            # value: same status/check keys and count, and every non-"disk"
            # message identical (which already proves the locale text itself
            # is unaffected).
            self.assertEqual(len(records_en), len(records_ja))
            for record_en, record_ja in zip(records_en, records_ja):
                self.assertEqual(record_en["status"], record_ja["status"])
                self.assertEqual(record_en["check"], record_ja["check"])
                if record_en["check"] == "disk":
                    continue
                self.assertEqual(record_en["message"], record_ja["message"])


if __name__ == "__main__":
    unittest.main()
