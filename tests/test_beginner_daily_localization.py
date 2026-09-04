"""Japanese localization of the Beginner/Daily CLI surface (#632).

Builds on #631's shared locale resolver/catalog (`lifetxt/i18n.py`). Every
test here drives the real installed entry point (`python -m lifetxt`) via
`run_cli`, confirming the localized text end to end while keeping command
names, options, Format 1.0 syntax, and every `--json` output byte-for-byte
identical across locales.
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


class TourLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_tour_headings(self):
        out, err, rc = run_cli("--lang", "ja", "tour")
        self.assertEqual(rc, 0)
        self.assertIn("lifetxt を30秒で体験", out)
        self.assertIn("次に試す", out)
        # Sample Format tokens and command examples stay canonical English.
        self.assertIn('[ ] T "Buy milk"', out)
        self.assertIn("lifetxt init", out)

    def test_tour_json_is_locale_invariant(self):
        out_en, _, rc_en = run_cli("tour", "--format", "json")
        out_ja, _, rc_ja = run_cli("--lang", "ja", "tour", "--format", "json")
        self.assertEqual(rc_en, 0)
        self.assertEqual(rc_ja, 0)
        self.assertEqual(json.loads(out_en), json.loads(out_ja))


class InitLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_init_completion_messages(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "--lang",
                "ja",
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--yes",
            )
            self.assertEqual(rc, 0)
            self.assertIn("書き込みました", out)
            self.assertIn("次に:", out)
            self.assertTrue(os.path.exists(life_file))
            self.assertTrue(os.path.exists(config_file))

    def test_english_default_init_is_unaffected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            life_file = os.path.join(tmpdir, "life.txt")
            config_file = os.path.join(tmpdir, ".lifetxt.json")
            out, err, rc = run_cli(
                "init",
                "--file",
                life_file,
                "--config-output",
                config_file,
                "--yes",
            )
            self.assertEqual(rc, 0)
            self.assertIn("Wrote", out)
            self.assertIn("Next:", out)


class TodayLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_today_headings(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "today", path)
            self.assertEqual(rc, 0)
            self.assertIn("次のアクション", out)
        finally:
            os.unlink(path)

    def test_today_json_is_locale_invariant(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out_en, _, rc_en = run_cli("today", path, "--json")
            out_ja, _, rc_ja = run_cli("--lang", "ja", "today", path, "--json")
            self.assertEqual(rc_en, 0)
            self.assertEqual(rc_ja, 0)
            self.assertEqual(json.loads(out_en), json.loads(out_ja))
        finally:
            os.unlink(path)


class DoneCompleteLocalizationTests(unittest.TestCase):
    def test_lang_ja_translates_done_success_message(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "done", path, "--line", "1")
            self.assertEqual(rc, 0)
            self.assertIn("完了しました", out)
        finally:
            os.unlink(path)

    def test_lang_ja_translates_already_done_message(self):
        path = _make_file("[x] T Buy_milk done:2026-01-01\n")
        try:
            out, err, rc = run_cli("--lang", "ja", "done", path, "--line", "1")
            self.assertEqual(rc, 0)
            self.assertIn("既に完了しています", out)
        finally:
            os.unlink(path)

    def test_english_default_done_is_unaffected(self):
        path = _make_file("[ ] T Buy_milk\n")
        try:
            out, err, rc = run_cli("done", path, "--line", "1")
            self.assertEqual(rc, 0)
            self.assertIn("Done:", out)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
