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


class ReportValidateCliTests(unittest.TestCase):
    def test_valid_v1_profile_reports_ok(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            out, code = _run(["validate", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertEqual(out, "weekly: OK\n")

    def test_valid_v2_profile_reports_ok(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "sections": [{"type": "review"}],
                        "scope": {"project": "home"},
                    }
                }
            )
            out, code = _run(["validate", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertEqual(out, "weekly: OK\n")

    def test_invalid_profile_fails_naming_the_reason(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "nope"}]}}
            )
            out, code = _run(["validate", "weekly"], config_path)
        self.assertEqual(code, 1)
        self.assertIn("weekly: FAIL:", out)
        self.assertIn("Unknown report section type", out)

    def test_invalid_output_placeholder_is_caught_without_writing_anything(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "output": "{nope}.md"}}
            )
            out, code = _run(["validate", "weekly"], config_path)
        self.assertEqual(code, 1)
        self.assertIn("Unknown report output placeholder", out)
        self.assertFalse(os.path.exists(os.path.join(ws.tmp.name, "nope.md")))

    def test_unknown_profile_name_fails_loudly(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            with self.assertRaisesRegex(ValueError, "Report profile not found"):
                _run(["validate", "nope"], config_path)

    def test_no_name_and_no_all_is_rejected(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            with self.assertRaisesRegex(ValueError, "NAME or --all"):
                _run(["validate"], config_path)

    def test_name_and_all_together_is_rejected(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            with self.assertRaisesRegex(ValueError, "not both"):
                _run(["validate", "weekly", "--all"], config_path)

    def test_all_reports_every_profile_and_does_not_stop_at_the_first_failure(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "a-broken": {
                        "period": "weekly",
                        "sections": [{"type": "nope"}],
                    },
                    "b-ok": {"period": "weekly"},
                }
            )
            out, code = _run(["validate", "--all"], config_path)
        self.assertEqual(code, 1)
        self.assertIn("a-broken: FAIL:", out)
        self.assertIn("b-ok: OK", out)

    def test_all_with_only_valid_profiles_exits_zero(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"a": {"period": "weekly"}, "b": {"period": "daily"}}
            )
            out, code = _run(["validate", "--all"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("a: OK", out)
        self.assertIn("b: OK", out)

    def test_all_with_no_profiles_configured_is_ok_and_empty(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({})
            out, code = _run(["validate", "--all"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("No report profiles configured", out)

    def test_json_format_single_profile(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            out, code = _run(["validate", "weekly", "--format", "json"], config_path)
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed, {"name": "weekly", "ok": True})

    def test_json_format_all_profiles_is_deterministic(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "a-broken": {
                        "period": "weekly",
                        "sections": [{"type": "nope"}],
                    },
                    "b-ok": {"period": "weekly"},
                }
            )
            out, code = _run(["validate", "--all", "--format", "json"], config_path)
        self.assertEqual(code, 1)
        parsed = json.loads(out)
        self.assertFalse(parsed["ok"])
        names = [entry["name"] for entry in parsed["profiles"]]
        self.assertEqual(names, ["a-broken", "b-ok"])
        self.assertFalse(parsed["profiles"][0]["ok"])
        self.assertIn("error", parsed["profiles"][0])
        self.assertTrue(parsed["profiles"][1]["ok"])
        self.assertNotIn("error", parsed["profiles"][1])

    def test_validate_never_touches_life_txt_or_the_filesystem(self):
        # A broken workspace path (no readable life.txt) must not stop
        # `report validate` from reporting a profile-configuration result --
        # validation is a pure config check, never a life.txt read.
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            os.unlink(ws.life_path)
            out, code = _run(["validate", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertEqual(out, "weekly: OK\n")

    def test_an_unrelated_broken_profile_does_not_block_validating_a_good_one(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "broken": {
                        "period": "weekly",
                        "sections": [{"type": "nope"}],
                    },
                    "good": {"period": "weekly"},
                }
            )
            out, code = _run(["validate", "good"], config_path)
        self.assertEqual(code, 0)
        self.assertEqual(out, "good: OK\n")


class ReportInspectCliTests(unittest.TestCase):
    def test_inspect_v1_profile_text(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "output": "out/{iso_year}-W{iso_week}.md",
                        "project": "home",
                    }
                }
            )
            out, code = _run(["inspect", "weekly"], config_path)
        self.assertEqual(code, 0)
        self.assertIn("weekly: lifetxt-report-v1 (weekly)", out)
        self.assertIn("output: out/{iso_year}-W{iso_week}.md ->", out)
        self.assertIn("scope: project=home", out)
        self.assertFalse(os.path.exists(os.path.join(ws.tmp.name, "out")))

    def test_inspect_v2_profile_json_matches_preview_period_and_scope(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "sections": [{"type": "stats", "group": "daily"}],
                        "scope": {"project": "home", "open": True},
                        "compare": "previous",
                    }
                }
            )
            inspect_out, inspect_code = _run(
                ["inspect", "weekly", "--format", "json"], config_path
            )
            preview_out, _preview_code = _run(
                ["preview", "weekly", "--format", "json"], config_path
            )
        self.assertEqual(inspect_code, 0)
        inspected = json.loads(inspect_out)
        previewed = json.loads(preview_out)
        self.assertEqual(inspected["schema"], "lifetxt-report-v2")
        self.assertEqual(inspected["period"]["start"], previewed["period_start"])
        self.assertEqual(inspected["period"]["end"], previewed["period_end"])
        self.assertEqual(inspected["scope"], {"project": "home", "open": True})
        self.assertEqual(inspected["compare"], "previous")
        self.assertEqual(
            inspected["sections"],
            [{"type": "stats", "title": None, "options": {"group": "daily"}}],
        )
        # inspect never renders body content: no section "data"/"findings" key.
        self.assertNotIn("data", json.dumps(inspected["sections"]))

    def test_inspect_date_and_previous_use_the_same_selector_as_preview(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, code = _run(
                ["inspect", "weekly", "--date", "2026-01-15", "--format", "json"],
                config_path,
            )
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["period"]["start"], "2026-01-12")
        self.assertEqual(parsed["period"]["end"], "2026-01-18")

    def test_inspect_date_and_previous_are_mutually_exclusive(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            with self.assertRaises(ValueError):
                _run(
                    [
                        "inspect",
                        "weekly",
                        "--date",
                        "2026-01-15",
                        "--previous",
                        "--format",
                        "json",
                    ],
                    config_path,
                )

    def test_inspect_invalid_profile_fails_through_the_same_validator(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "nope"}]}}
            )
            with self.assertRaisesRegex(ValueError, "Unknown report section type"):
                _run(["inspect", "weekly"], config_path)

    def test_inspect_no_output_configured_reports_none(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "sections": [{"type": "review"}]}}
            )
            out, code = _run(["inspect", "weekly", "--format", "json"], config_path)
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out)["output"])

    def test_inspect_relative_and_absolute_output_paths_resolve(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"relative": {"period": "weekly", "output": "out/report.md"}}
            )
            out, _code = _run(["inspect", "relative", "--format", "json"], config_path)
            resolved = json.loads(out)["output"]["path"]
        self.assertTrue(os.path.isabs(resolved))
        self.assertTrue(resolved.endswith(os.path.join("out", "report.md")))

    def test_inspect_never_writes_the_output_file(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {"weekly": {"period": "weekly", "output": "generated.md"}}
            )
            _run(["inspect", "weekly"], config_path)
            self.assertFalse(os.path.exists(os.path.join(ws.tmp.name, "generated.md")))

    def test_inspect_never_writes_share_md(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config({"weekly": {"period": "weekly"}})
            cwd = os.getcwd()
            os.chdir(ws.tmp.name)
            try:
                _run(["inspect", "weekly"], config_path)
                self.assertFalse(os.path.exists(os.path.join(ws.tmp.name, "share.md")))
            finally:
                os.chdir(cwd)

    def test_inspect_email_configured_flag_never_exposes_env_var_values(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "weekly": {
                        "period": "weekly",
                        "email": {
                            "to": "me@example.com",
                            "smtp_pass_env": "LIFETXT_SMTP_PASS",
                        },
                    }
                }
            )
            with mock.patch.dict(
                os.environ, {"LIFETXT_SMTP_PASS": "super-secret-value"}
            ):
                out, code = _run(["inspect", "weekly", "--format", "json"], config_path)
        self.assertEqual(code, 0)
        parsed = json.loads(out)
        self.assertTrue(parsed["email_configured"])
        self.assertNotIn("super-secret-value", out)
        self.assertNotIn("smtp_pass_env", out)

    def test_an_unrelated_broken_profile_does_not_block_inspecting_a_good_one(self):
        with _TempWorkspace() as ws:
            config_path = ws.write_config(
                {
                    "broken": {
                        "period": "weekly",
                        "sections": [{"type": "nope"}],
                    },
                    "good": {"period": "weekly", "sections": [{"type": "review"}]},
                }
            )
            out, code = _run(["inspect", "good", "--format", "json"], config_path)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["report"], "good")


if __name__ == "__main__":
    unittest.main()
