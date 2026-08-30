import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import report_cli

LIFE_TEXT = """\
[x] T Buy_milk done:2026-08-25 project:home
[ ] T Overdue_task due:2026-08-20 project:work
"""


class _TempWorkspace:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        directory = self.tmp.name
        self.life_path = os.path.join(directory, "life.txt")
        with open(self.life_path, "w", encoding="utf-8") as handle:
            handle.write(LIFE_TEXT)
        self.config_path = os.path.join(directory, ".lifetxt.json")
        return self

    def write_config(self, reports):
        config = {"paths": [self.life_path], "reports": reports}
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        return self.config_path

    def __exit__(self, *exc_info):
        self.tmp.cleanup()


def _run(argv, config_path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = report_cli.main(argv, config_path=config_path)
    return out.getvalue(), code


class ReportV2ProfileValidationTests(unittest.TestCase):
    def test_v2_profile_accepts_sections_format_audience_compare(self):
        profile = report_cli._validate_profile(
            "weekly",
            {
                "period": "weekly",
                "sections": [{"type": "review"}, {"type": "stats"}],
                "format": "json",
                "audience": "private",
                "compare": "previous",
            },
        )
        self.assertEqual(profile["format"], "json")
        self.assertEqual(profile["compare"], "previous")

    def test_v2_key_without_sections_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Report v2 key"):
            report_cli._validate_profile(
                "weekly", {"period": "weekly", "format": "json"}
            )

    def test_unknown_section_type_rejected_at_profile_load(self):
        with self.assertRaises(ValueError):
            report_cli._validate_profile(
                "weekly", {"period": "weekly", "sections": [{"type": "nope"}]}
            )

    def test_external_audience_rejects_unsafe_section(self):
        with self.assertRaises(ValueError):
            report_cli._validate_profile(
                "weekly",
                {
                    "period": "weekly",
                    "audience": "external",
                    "sections": [{"type": "review"}],
                },
            )

    def test_email_config_requires_to(self):
        with self.assertRaisesRegex(ValueError, "email.to"):
            report_cli._validate_profile(
                "weekly", {"period": "weekly", "email": {"subject": "x"}}
            )

    def test_v1_profile_may_declare_email(self):
        profile = report_cli._validate_profile(
            "weekly", {"period": "weekly", "email": {"to": "me@example.com"}}
        )
        self.assertEqual(profile["email"]["to"], "me@example.com")

    def test_scope_key_without_sections_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Report v2 key"):
            report_cli._validate_profile(
                "weekly", {"period": "weekly", "scope": {"project": ["x"]}}
            )

    def test_v2_profile_resolves_explicit_scope(self):
        profile = report_cli._validate_profile(
            "weekly",
            {
                "period": "weekly",
                "sections": [{"type": "review"}],
                "scope": {"project": ["home"], "open": True},
            },
        )
        self.assertEqual(profile["scope"], {"project": ["home"], "open": True})

    def test_v2_profile_with_no_scope_defaults_to_empty(self):
        profile = report_cli._validate_profile(
            "weekly", {"period": "weekly", "sections": [{"type": "review"}]}
        )
        self.assertEqual(profile["scope"], {})

    def test_legacy_top_level_project_becomes_scope_alias(self):
        profile = report_cli._validate_profile(
            "weekly",
            {
                "period": "weekly",
                "project": "home",
                "sections": [{"type": "review"}],
            },
        )
        self.assertEqual(profile["scope"]["project"], "home")

    def test_conflicting_legacy_and_scope_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting"):
            report_cli._validate_profile(
                "weekly",
                {
                    "period": "weekly",
                    "project": "home",
                    "scope": {"project": "work"},
                    "sections": [{"type": "review"}],
                },
            )

    def test_matching_legacy_and_scope_values_are_not_a_conflict(self):
        profile = report_cli._validate_profile(
            "weekly",
            {
                "period": "weekly",
                "project": "home",
                "scope": {"project": "home", "open": True},
                "sections": [{"type": "review"}],
            },
        )
        self.assertEqual(profile["scope"], {"project": "home", "open": True})


class ReportV2CliEndToEndTests(unittest.TestCase):
    def test_preview_v2_profile_renders_markdown_by_default(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, code = _run(["preview", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("report_schema: lifetxt-report-v2", out)
        self.assertIn("## Review", out)
        self.assertIn("Completed tasks: 1", out)

    def test_scope_restricts_every_section_to_the_scoped_project(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "home-only": {
                        "period": "weekly",
                        "scope": {"project": "home"},
                        "sections": [{"type": "review"}],
                    },
                    "work-only": {
                        "period": "weekly",
                        "scope": {"project": "work"},
                        "sections": [{"type": "review"}],
                    },
                }
            )
            home_out, _ = _run(
                ["preview", "home-only", "--format", "json"], config_path
            )
            work_out, _ = _run(
                ["preview", "work-only", "--format", "json"], config_path
            )
        home_model = json.loads(home_out)
        work_model = json.loads(work_out)
        self.assertEqual(home_model["sections"][0]["data"]["completed_tasks"], 1)
        self.assertEqual(work_model["sections"][0]["data"]["completed_tasks"], 0)

    def test_preview_format_override_produces_json(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "stats"}]}}
            )
            out, code = _run(["preview", "weekly", "--format", "json"], config_path)
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["report_schema"], "lifetxt-report-v2")

    def test_format_override_rejected_for_v1_profile(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            with self.assertRaises(ValueError):
                _run(["preview", "weekly", "--format", "json"], config_path)

    def test_date_anchor_selects_historical_period(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, code = _run(
                ["preview", "weekly", "--date", "2026-01-15", "--format", "json"],
                config_path,
            )
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["period_start"], "2026-01-12")
        self.assertEqual(parsed["period_end"], "2026-01-18")

    def test_date_and_previous_are_mutually_exclusive(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            with self.assertRaises(ValueError):
                _run(
                    [
                        "preview",
                        "weekly",
                        "--date",
                        "2026-01-15",
                        "--previous",
                        "--format",
                        "json",
                    ],
                    config_path,
                )

    def test_previous_flag_shifts_the_period_back_one_week_relative_to_today(self):
        import datetime

        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            with mock.patch.object(
                report_cli, "timezone_today", return_value=datetime.date(2026, 8, 26)
            ):
                out_current, _ = _run(
                    ["preview", "weekly", "--format", "json"], config_path
                )
                out_previous, _ = _run(
                    ["preview", "weekly", "--previous", "--format", "json"],
                    config_path,
                )
        current = json.loads(out_current)
        previous = json.loads(out_previous)
        self.assertEqual(current["period_start"], "2026-08-24")
        self.assertEqual(previous["period_start"], "2026-08-17")

    def test_run_writes_v2_report_to_configured_output(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "sections": [{"type": "review"}],
                        "output": "out.md",
                    }
                }
            )
            out, code = _run(["run", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("Wrote report weekly", out)

    def test_v1_report_still_uses_share_delegation_unchanged(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            out, code = _run(["preview", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("report_schema: lifetxt-report-v1", out)
        # The real rendered share body, not just share's file-write confirmation.
        self.assertIn("## Items", out)
        self.assertNotIn("Wrote share.md", out)

    def test_v1_report_preview_leaves_no_stray_share_file_in_cwd(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            cwd = os.getcwd()
            os.chdir(ws.tmp.name)
            try:
                _run(["preview", "weekly"], config_path)
                self.assertFalse(os.path.exists(os.path.join(ws.tmp.name, "share.md")))
            finally:
                os.chdir(cwd)


class ReportSendTests(unittest.TestCase):
    def test_send_requires_email_config(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            with self.assertRaisesRegex(ValueError, "no `email` configuration"):
                _run(["send", "weekly", "--dry-run"], config_path)

    def test_send_dry_run_prints_without_smtp(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "sections": [{"type": "review"}],
                        "email": {
                            "to": "me@example.com",
                            "subject": "Weekly {period_start} - {period_end}",
                        },
                    }
                }
            )
            with mock.patch("smtplib.SMTP") as smtp_cls:
                out, code = _run(["send", "weekly", "--dry-run"], config_path)
        self.assertEqual(code, 0)
        smtp_cls.assert_not_called()
        self.assertIn("[dry-run]", out)
        self.assertIn("me@example.com", out)

    def test_send_v1_profile_email_dry_run(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "email": {"to": "me@example.com"},
                    }
                }
            )
            with mock.patch("smtplib.SMTP") as smtp_cls:
                out, code = _run(["send", "weekly", "--dry-run"], config_path)
        self.assertEqual(code, 0)
        smtp_cls.assert_not_called()
        self.assertIn("[dry-run]", out)


if __name__ == "__main__":
    unittest.main()
