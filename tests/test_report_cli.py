import argparse
import contextlib
import datetime
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from lifetxt import config_registry
from lifetxt import entrypoint
from lifetxt import report_cli
from lifetxt.report_config import install_report_config_registry
from lifetxt.schema_extensions_v5 import schema_bundle_v5


class ReportPeriodTests(unittest.TestCase):
    def test_resolve_periods(self):
        day = datetime.date(2026, 8, 25)
        self.assertEqual(report_cli.resolve_period("daily", day), (day, day))
        self.assertEqual(
            report_cli.resolve_period("weekly", day),
            (datetime.date(2026, 8, 24), datetime.date(2026, 8, 30)),
        )
        self.assertEqual(
            report_cli.resolve_period("monthly", day),
            (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31)),
        )

    def test_output_placeholders(self):
        start = datetime.date(2026, 1, 1)
        self.assertEqual(
            report_cli.resolve_output_template(
                "{date}/{year}-{month}/{iso_year}-W{iso_week}.md", start
            ),
            "2026-01-01/2026-01/2026-W01.md",
        )
        with self.assertRaisesRegex(ValueError, "Unknown report output placeholder"):
            report_cli.resolve_output_template("{unknown}.md", start)
        with self.assertRaisesRegex(ValueError, "do not accept format specs"):
            report_cli.resolve_output_template("{year:04}.md", start)


class ReportProfileTests(unittest.TestCase):
    def test_profile_defaults_and_strict_validation(self):
        profiles = report_cli._profiles(
            {"reports": {"weekly": {"period": "weekly"}}}
        )
        self.assertEqual(profiles["weekly"]["mode"], "replace")
        self.assertTrue(profiles["weekly"]["frontmatter"])

        bad_values = (
            {"period": "quarterly"},
            {"period": "weekly", "mode": "merge"},
            {"period": "weekly", "frontmatter": "yes"},
            {"period": "weekly", "unexpected": True},
        )
        for profile in bad_values:
            with self.subTest(profile=profile):
                with self.assertRaises(ValueError):
                    report_cli._profiles({"reports": {"bad": profile}})

    def test_share_arguments_include_real_period_bounds_and_filters(self):
        argv = report_cli._share_argv(
            {
                "period": "weekly",
                "title": "Review",
                "project": "research",
                "type": "T",
                "tag": "weekly",
                "open": True,
            },
            datetime.date(2026, 8, 24),
            datetime.date(2026, 8, 30),
            config_path=".lifetxt.json",
            workspace_name="personal",
        )
        self.assertEqual(argv[:4], ["--config", ".lifetxt.json", "--workspace", "personal"])
        self.assertIn("share", argv)
        self.assertEqual(argv[argv.index("--after") + 1], "2026-08-24")
        self.assertEqual(argv[argv.index("--before") + 1], "2026-08-30")
        self.assertIn("--open", argv)
        self.assertEqual(argv[argv.index("--project") + 1], "research")

    def test_frontmatter_is_versioned_and_identifies_period(self):
        generated = datetime.datetime.fromisoformat("2026-08-25T18:05:00+09:00")
        text = report_cli._frontmatter(
            "weekly",
            {"period": "weekly"},
            datetime.date(2026, 8, 24),
            datetime.date(2026, 8, 30),
            generated,
            "Asia/Tokyo",
        )
        self.assertIn("generator: lifetxt", text)
        self.assertIn("report_schema: lifetxt-report-v1", text)
        self.assertIn('report: "weekly"', text)
        self.assertIn("period_start: 2026-08-24", text)
        self.assertIn("period_end: 2026-08-30", text)
        self.assertIn('timezone: "Asia/Tokyo"', text)


class ReportOutputTests(unittest.TestCase):
    def test_replace_create_and_append_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "nested", "report.md")
            report_cli._write_report(path, "first\n", "replace")
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "first\n")

            with self.assertRaisesRegex(ValueError, "already exists"):
                report_cli._write_report(path, "nope\n", "create")

            report_cli._write_report(path, "second\n", "append")
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "first\nsecond\n")

    def test_preview_does_not_write_configured_target(self):
        args = argparse.Namespace(name="weekly")
        config = {
            "reports": {
                "weekly": {
                    "period": "weekly",
                    "output": "must-not-be-written.md",
                }
            }
        }
        out = io.StringIO()
        with mock.patch.object(
            report_cli,
            "render_report",
            return_value=(
                "# Preview\n",
                datetime.date(2026, 8, 24),
                datetime.date(2026, 8, 30),
            ),
        ):
            with contextlib.redirect_stdout(out):
                result = report_cli._command_preview(args, config)
        self.assertEqual(result, 0)
        self.assertEqual(out.getvalue(), "# Preview\n")
        self.assertFalse(os.path.exists("must-not-be-written.md"))

    def test_run_resolves_relative_output_from_config_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = os.path.join(directory, ".lifetxt.json")
            config = {
                "_path": config_path,
                "reports": {
                    "weekly": {
                        "period": "weekly",
                        "output": "generated/{iso_year}-W{iso_week}.md",
                    }
                },
            }
            args = argparse.Namespace(name="weekly")
            with mock.patch.object(
                report_cli,
                "render_report",
                return_value=(
                    "# Weekly\n",
                    datetime.date(2026, 8, 24),
                    datetime.date(2026, 8, 30),
                ),
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = report_cli._command_run(args, config)
            self.assertEqual(result, 0)
            expected = os.path.join(directory, "generated", "2026-W35.md")
            with open(expected, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "# Weekly\n")

    def test_run_requires_output_but_preview_does_not(self):
        profile = report_cli._validate_profile("weekly", {"period": "weekly"})
        with self.assertRaisesRegex(ValueError, "missing required output"):
            report_cli._resolved_output(
                profile, datetime.date(2026, 8, 24), {"_path": "/tmp/config.json"}
            )


class ReportConfigContractTests(unittest.TestCase):
    def test_registry_metadata_supports_named_profiles(self):
        install_report_config_registry()
        metadata = config_registry.explain_key("reports.weekly.period")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata["allowed_values"], ["daily", "weekly", "monthly"])
        self.assertTrue(metadata["required"])
        self.assertEqual(
            config_registry.explain_key("reports.weekly.mode")["default"], "replace"
        )

    def test_generated_and_published_config_schema_include_reports(self):
        generated = schema_bundle_v5()["config-v1.schema.json"]
        report_schema = generated["properties"]["reports"]["additionalProperties"]
        self.assertEqual(report_schema["required"], ["period"])
        self.assertFalse(report_schema["additionalProperties"])
        self.assertEqual(
            report_schema["properties"]["mode"]["enum"],
            ["replace", "create", "append"],
        )

        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "dist",
            "schemas",
            "config-v1.schema.json",
        )
        with open(path, "r", encoding="utf-8") as handle:
            published = json.load(handle)
        self.assertEqual(published, generated)

    def test_entrypoint_routes_report_command(self):
        with mock.patch("lifetxt.report_cli.main", return_value=0) as report_main:
            self.assertEqual(entrypoint.main(["report", "list"]), 0)
        report_main.assert_called_once_with(
            ["report", "list"], config_path=None, workspace_name=None
        )


if __name__ == "__main__":
    unittest.main()
