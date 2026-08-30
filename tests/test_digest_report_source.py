"""`lifetxt digest --report NAME` uses a configured report profile as its
message source instead of the built-in review summary (#608)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.test_lifetxt import run_cli

LIFE_TEXT = "[x] T Buy_milk done:2026-08-25 project:home\n"


class _Workspace:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        directory = self.tmp.name
        self.life_path = os.path.join(directory, "life.txt")
        with open(self.life_path, "w", encoding="utf-8") as handle:
            handle.write(LIFE_TEXT)
        self.config_path = os.path.join(directory, ".lifetxt.json")
        return self

    def write_config(self, reports):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump({"paths": [self.life_path], "reports": reports}, handle)
        return self.config_path

    def __exit__(self, *exc_info):
        self.tmp.cleanup()


class DigestReportSourceTests(unittest.TestCase):
    def test_digest_report_file_channel_writes_the_rendered_report(self):
        with _Workspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            digest_path = os.path.join(ws.tmp.name, "digest.md")
            out, err, rc = run_cli(
                "--config",
                config_path,
                "digest",
                "--report",
                "weekly",
                "--format",
                "file",
                "--path",
                digest_path,
            )
            self.assertEqual(rc, 0, err)
            text = Path(digest_path).read_text(encoding="utf-8")
            self.assertIn("report_schema: lifetxt-report-v2", text)
            self.assertIn("## Review", text)

    def test_digest_report_dry_run_email_shows_rendered_body(self):
        with _Workspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, err, rc = run_cli(
                "--config",
                config_path,
                "digest",
                "--report",
                "weekly",
                "--format",
                "email",
                "--to",
                "me@example.com",
                "--dry-run",
            )
            self.assertEqual(rc, 0, err)
            self.assertIn("[dry-run]", out)
            self.assertIn("report_schema: lifetxt-report-v2", out)

    def test_digest_report_unknown_profile_fails_loudly(self):
        with _Workspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, err, rc = run_cli(
                "--config",
                config_path,
                "digest",
                "--report",
                "nope",
                "--format",
                "file",
                "--path",
                os.path.join(ws.tmp.name, "digest.md"),
            )
            self.assertEqual(rc, 1)
            self.assertIn("Report profile not found", err)

    def test_digest_report_v1_profile_still_delegates_to_share(self):
        with _Workspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            digest_path = os.path.join(ws.tmp.name, "digest.md")
            out, err, rc = run_cli(
                "--config",
                config_path,
                "digest",
                "--report",
                "weekly",
                "--format",
                "file",
                "--path",
                digest_path,
            )
            self.assertEqual(rc, 0, err)
            text = Path(digest_path).read_text(encoding="utf-8")
            self.assertIn("report_schema: lifetxt-report-v1", text)

    def test_digest_without_report_flag_uses_review_summary_unchanged(self):
        with _Workspace() as ws:
            digest_path = os.path.join(ws.tmp.name, "digest.md")
            out, err, rc = run_cli(
                "digest",
                ws.life_path,
                "--month",
                "2026-08",
                "--format",
                "file",
                "--path",
                digest_path,
            )
            self.assertEqual(rc, 0, err)
            text = Path(digest_path).read_text(encoding="utf-8")
            self.assertIn("lifetxt digest", text)
            self.assertNotIn("report_schema", text)


if __name__ == "__main__":
    unittest.main()
