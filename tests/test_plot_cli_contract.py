"""Deterministic public plot data/output contracts for #1138."""

import datetime
import os
from pathlib import Path
import tempfile
from unittest import mock
import xml.etree.ElementTree as ET

from lifetxt import cli, entrypoint
from lifetxt.runtime_safety_v2 import install_cli_timezone_context
from lifetxt.timezone_policy import clock_context
from tests.test_core_cli_entrypoint import CliContractTestCase


FIXTURE = (
    "[x] T First done:2026-06-01 project:p elapsed:1h30m\n"
    "[x] T Middle done:2026-06-10 project:p\n"
    "[x] T Other done:2026-06-10 project:q elapsed:30m\n"
    "[x] T Last done:2026-06-30 project:p\n"
    "[x] T Before done:2026-05-31 project:p\n"
    "[x] T After done:2026-07-01 project:p\n"
    "[ ] T Open project:p\n"
    '[x] H "Read & Learn" done:2026-06-01 done:2026-06-10 done:2026-07-01 project:p\n'
    "[ ] H Walk project:p\n"
    "[N] J First created:2026-06-01 mood:happy project:p\n"
    "[N] J Last created:2026-06-30 mood:calm project:p\n"
    "[N] J Undated mood:happy project:p\n"
    "[N] J Outside created:2026-07-01 mood:sad project:p\n"
    "[ ] E Plan due:2026-06-01 do:2026-06-10 project:p\n"
    "[ ] D Last due:2026-06-30 project:p\n"
    "[ ] D Outside due:2026-07-01 project:p\n"
)


class PlotCliContractTests(CliContractTestCase):
    def setUp(self):
        super().setUp()
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.path = Path(directory) / "life.txt"
        self.path.write_text(FIXTURE, encoding="utf-8")
        self.config_path = Path(directory) / "config.json"
        self.config_path.write_text('{"timezone": "UTC"}', encoding="utf-8")
        install_cli_timezone_context(cli)
        self.stack.enter_context(
            mock.patch(
                "lifetxt.config.find_config_path", return_value=str(self.config_path)
            )
        )
        self.stack.enter_context(
            clock_context(datetime.datetime(2026, 6, 30, tzinfo=datetime.timezone.utc))
        )
        self.stack.enter_context(
            mock.patch.object(cli.os, "get_terminal_size", side_effect=OSError)
        )
        self.expected = {
            "Tasks Completed (weekly)": {"2026-W23": 1, "2026-W24": 2, "2026-W27": 1},
            "Habit Completions (total, 2026-06-01 to 2026-06-30)": {"Read & Learn": 2},
            "Mood Distribution (2026-06-01 to 2026-06-30)": {"calm": 1, "happy": 2},
            "Elapsed Time by Project": {"p": 90, "q": 30},
            "Deadline Density (weekly)": {"2026-W23": 1, "2026-W24": 1, "2026-W27": 1},
        }

    def run_plot(self, *options):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        original = self.path.read_bytes(), self.config_path.read_bytes()
        result = entrypoint.main(
            [
                "plot",
                str(self.path),
                "--from",
                "2026-06-01",
                "--to",
                "2026-06-30",
                *options,
            ]
        )
        self.assertEqual(
            (self.path.read_bytes(), self.config_path.read_bytes()), original
        )
        return result

    def svg_data(self, output):
        root = ET.fromstring(output)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
        result = {}
        section = None
        label = None
        for element in root:
            if element.tag != "{http://www.w3.org/2000/svg}text":
                continue
            if element.get("class") == "section":
                section = element.text
                result[section] = {}
            elif element.get("class") == "axis":
                result[section][label] = int(element.text)
            elif section is not None and element.get("class") is None:
                label = element.text
        return result

    def test_all_chart_families_and_selection_render_fixture_values(self):
        for chart, title in zip(
            ("tasks", "habits", "mood", "elapsed", "deadlines", "all"),
            (*self.expected, None),
        ):
            with self.subTest(chart=chart):
                self.assertEqual(self.run_plot("--chart", chart, "--format", "svg"), 0)
                expected = (
                    self.expected if title is None else {title: self.expected[title]}
                )
                self.assertEqual(self.svg_data(self.stdout.getvalue()), expected)
                self.assertEqual(self.stderr.getvalue(), "")

    def test_task_and_deadline_buckets_and_inclusive_bounds(self):
        for group, tasks, deadlines in (
            (
                "daily",
                {"2026-06-01": 1, "2026-06-10": 2, "2026-06-30": 1},
                {"2026-06-01": 1, "2026-06-10": 1, "2026-06-30": 1},
            ),
            (
                "weekly",
                {"2026-W23": 1, "2026-W24": 2, "2026-W27": 1},
                {"2026-W23": 1, "2026-W24": 1, "2026-W27": 1},
            ),
            ("monthly", {"2026-06": 4}, {"2026-06": 3}),
        ):
            for chart, title, values in (
                ("tasks", "Tasks Completed", tasks),
                ("deadlines", "Deadline Density", deadlines),
            ):
                with self.subTest(chart=chart, group=group):
                    self.assertEqual(
                        self.run_plot(
                            "--chart", chart, "--group", group, "--format", "svg"
                        ),
                        0,
                    )
                    self.assertEqual(
                        self.svg_data(self.stdout.getvalue()),
                        {"%s (%s)" % (title, group): values},
                    )
                    self.assertEqual(self.stderr.getvalue(), "")

    def test_project_filter_applies_to_real_chart_data(self):
        self.assertEqual(self.run_plot("--project", "p", "--format", "svg"), 0)
        expected = dict(self.expected)
        expected["Tasks Completed (weekly)"] = {
            "2026-W23": 1,
            "2026-W24": 1,
            "2026-W27": 1,
        }
        expected["Elapsed Time by Project"] = {"p": 90}
        self.assertEqual(self.svg_data(self.stdout.getvalue()), expected)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_text_width_and_auto_detection_fallback(self):
        for width, bars in ((40, 10), (60, 30), (200, 40), (0, 40)):
            with self.subTest(width=width):
                self.assertEqual(
                    self.run_plot(
                        "--chart", "tasks", "--group", "monthly", "--width", str(width)
                    ),
                    0,
                )
                self.assertEqual(
                    self.stdout.getvalue(),
                    "\n## Tasks Completed (monthly)\n  2026-06      %s 4\n\n"
                    % ("#" * bars),
                )
                self.assertEqual(self.stderr.getvalue(), "")
        with mock.patch.object(
            cli.os, "get_terminal_size", return_value=os.terminal_size((50, 20))
        ):
            self.assertEqual(self.run_plot("--chart", "tasks", "--group", "monthly"), 0)
        self.assertIn("#" * 20 + " 4\n", self.stdout.getvalue())

    def test_text_all_charts_has_counts_and_formatted_elapsed(self):
        self.assertEqual(self.run_plot("--width", "40"), 0)
        output = self.stdout.getvalue()
        for title in self.expected:
            self.assertIn("## " + title + "\n", output)
        self.assertIn("2026-W24     ########## 2\n", output)
        self.assertIn("calm         #####..... 1\n", output)
        self.assertIn("happy        ########## 2\n", output)
        self.assertIn("p              ########## 1h30m\n", output)
        self.assertIn("q              ###....... 30m\n", output)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_sparklines_show_fixture_trends_and_empty_input(self):
        self.assertEqual(self.run_plot("--sparkline", "--width", "40"), 0)
        output = self.stdout.getvalue()
        self.assertIn("  Tasks:     ▄█▄  (1..2)\n", output)
        self.assertIn("  Habits:    ██  (1..1)\n", output)
        self.assertIn("  Deadlines: ███  (1..1)\n", output)
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(self.run_plot("--sparkline", "--width", "40"), 0)
        self.assertEqual(
            self.stdout.getvalue(),
            "\n## Sparklines\n  Tasks:     (empty)\n  Habits:    (empty)\n  Deadlines: (empty)\n\n",
        )
        self.assertEqual(self.stderr.getvalue(), "")

    def test_empty_text_and_svg_keep_no_data_contract(self):
        self.path.write_text("", encoding="utf-8")
        self.assertEqual(self.run_plot(), 0)
        self.assertEqual(self.stdout.getvalue(), "\n")
        self.assertEqual(self.run_plot("--format", "svg"), 0)
        output = self.stdout.getvalue()
        self.assertEqual(self.svg_data(output), {})
        self.assertIn("No plot data.", output)
        self.assertEqual(self.stderr.getvalue(), "")

    def test_svg_output_writes_only_requested_temporary_file(self):
        output_path = self.path.with_name("chart.svg")
        self.assertEqual(self.run_plot("--format", "svg", "-o", str(output_path)), 0)
        self.assertEqual(
            self.svg_data(output_path.read_text(encoding="utf-8")), self.expected
        )
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")
        self.assertEqual(
            {path.name for path in self.path.parent.iterdir()},
            {"life.txt", "config.json", "chart.svg"},
        )

    def test_png_requires_output_for_empty_and_populated_input(self):
        for content in (FIXTURE, ""):
            with self.subTest(empty=not content):
                self.path.write_text(content, encoding="utf-8")
                with mock.patch.object(cli, "_plot_data_to_png") as renderer:
                    self.assert_error(
                        self.run_plot("--format", "png"),
                        "--format png requires -o/--output.",
                    )
                renderer.assert_not_called()

    def test_png_routes_real_aggregate_data_and_dependency_errors(self):
        output_path = str(self.path.with_name("chart.png"))
        with mock.patch.object(cli, "_plot_data_to_png") as renderer:
            self.assertEqual(self.run_plot("--format", "png", "-o", output_path), 0)
        renderer.assert_called_once_with(self.expected, output_path)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")
        message = (
            "--format png requires matplotlib. Install matplotlib or use --format svg."
        )
        with mock.patch.object(
            cli, "_plot_data_to_png", side_effect=ValueError(message)
        ):
            self.assert_error(
                self.run_plot("--format", "png", "-o", output_path), message
            )
