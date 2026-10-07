"""Public plot date contracts for #1136; no user configuration or writes."""

import datetime
import itertools
from pathlib import Path
import tempfile
from unittest import mock

from lifetxt import cli, entrypoint
from lifetxt.runtime_safety_v2 import install_cli_timezone_context
from lifetxt.timezone_policy import clock_context
from tests.test_core_cli_entrypoint import CliContractTestCase


class PlotRangeValidationTests(CliContractTestCase):
    def setUp(self):
        super().setUp()
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "life.txt"
        install_cli_timezone_context(cli)
        config_path = Path(directory) / "config.json"
        config_path.write_text('{"timezone": "UTC"}', encoding="utf-8")
        self.stack.enter_context(
            mock.patch("lifetxt.config.find_config_path", return_value=str(config_path))
        )
        self.stack.enter_context(
            clock_context(datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc))
        )

    def run_plot(self, *options):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        original = self.path.read_bytes()
        result = entrypoint.main(["plot", str(self.path), "--chart", "tasks", *options])
        self.assertEqual(self.path.read_bytes(), original)
        return result

    def test_invalid_explicit_bounds_fail_for_empty_and_populated_input(self):
        for option, invalid, content in itertools.product(
            ("--from", "--to"),
            ("bad", "2026-02-30", ""),
            ("", "[x] T Done done:2026-06-10\n"),
        ):
            with self.subTest(option=option, invalid=invalid, empty=not content):
                self.path.write_text(content, encoding="utf-8")
                options = ["--from", "2026-06-01", "--to", "2026-06-30"]
                options[options.index(option) + 1] = invalid
                self.assert_error(
                    self.run_plot(*options),
                    "Invalid %s date %r. Use YYYY-MM-DD." % (option[2:], invalid),
                )

    def test_inclusive_bounds_preserve_existing_datetime_prefix_parsing(self):
        self.path.write_text(
            "[x] T Before done:2026-05-31\n"
            "[x] T First done:2026-06-01\n"
            "[x] T Last done:2026-06-30\n"
            "[x] T After done:2026-07-01\n",
            encoding="utf-8",
        )
        self.assertEqual(
            self.run_plot(
                "--from",
                "2026-06-01T12:00:00Z",
                "--to",
                "2026-06-30T12:00:00Z",
                "--group",
                "monthly",
                "--width",
                "40",
            ),
            0,
        )
        self.assertIn("2026-06      ########## 2", self.stdout.getvalue())
        self.assertNotIn("2026-05", self.stdout.getvalue())
        self.assertNotIn("2026-07", self.stdout.getvalue())
        self.assertEqual(self.stderr.getvalue(), "")

    def test_default_bounds_use_frozen_workspace_clock(self):
        self.path.write_text(
            "[x] T Before done:2026-03-31\n"
            "[x] T First done:2026-04-01\n"
            "[x] T Last done:2026-06-30\n"
            "[x] T After done:2026-07-01\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_plot("--group", "daily", "--width", "40"), 0)
        output = self.stdout.getvalue()
        self.assertIn("2026-04-01", output)
        self.assertIn("2026-06-30", output)
        self.assertNotIn("2026-03-31", output)
        self.assertNotIn("2026-07-01", output)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_default_bounds_follow_configured_timezone_date(self):
        config_path = self.path.with_name("config.json")
        config_path.write_text('{"timezone": "Asia/Tokyo"}', encoding="utf-8")
        self.path.write_text(
            "[x] T Before done:2026-04-01\n"
            "[x] T First done:2026-04-02\n"
            "[x] T Last done:2026-07-01\n"
            "[x] T After done:2026-07-02\n",
            encoding="utf-8",
        )
        with clock_context(
            datetime.datetime(2026, 6, 30, 18, tzinfo=datetime.timezone.utc)
        ):
            self.assertEqual(self.run_plot("--group", "daily", "--width", "40"), 0)
        output = self.stdout.getvalue()
        self.assertIn("2026-04-02", output)
        self.assertIn("2026-07-01", output)
        self.assertNotIn("2026-04-01", output)
        self.assertNotIn("2026-07-02", output)
        self.assertEqual(self.stderr.getvalue(), "")
