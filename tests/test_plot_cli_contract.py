"""Deterministic plot CLI chart/output contracts (#1138)."""

import os
import tempfile
from unittest import mock

from lifetxt import cli, entrypoint
from tests.test_core_cli_entrypoint import CliContractTestCase


PLOT_SOURCE = (
    '[x] T "Alpha first" done:2026-06-01 project:alpha due:2026-06-01\n'
    '[x] T "Alpha second" done:2026-06-07 project:alpha due:2026-06-30\n'
    '[x] T "Beta task" done:2026-06-08 project:beta do:2026-06-08\n'
    '[x] H "Stretch" done:2026-06-01 project:alpha\n'
    '[x] H "Stretch" done:2026-06-02 project:alpha\n'
    '[N] J "Mood one" mood:happy on:2026-06-01 project:alpha\n'
    '[N] J "Mood two" mood:calm on:2026-06-08 project:beta\n'
    '[x] T "Timed alpha" done:2026-06-15 elapsed:90m project:alpha\n'
    '[x] T "Timed beta" done:2026-06-15 elapsed:30m project:beta\n'
)


class PlotCliContractTests(CliContractTestCase):
    def _make_file(self, text=PLOT_SOURCE):
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        handle.write(text)
        handle.flush()
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def _run(self, *argv):
        self.stdout.seek(0)
        self.stdout.truncate()
        self.stderr.seek(0)
        self.stderr.truncate()
        code = entrypoint.main(list(argv))
        return code, self.stdout.getvalue(), self.stderr.getvalue()

    def test_chart_families_render_fixture_derived_values(self):
        path = self._make_file()
        cases = (
            ("tasks", ("Tasks Completed (daily)", "2026-06-01", "2026-06-08")),
            ("habits", ("Habit Completions", "Stretch", "2")),
            ("mood", ("Mood Distribution", "happy", "calm")),
            ("elapsed", ("Elapsed Time by Project", "alpha", "1h30m", "beta", "30m")),
            ("deadlines", ("Deadline Density (daily)", "2026-06-01", "2026-06-30")),
        )
        for chart, expected in cases:
            with self.subTest(chart=chart):
                code, out, err = self._run(
                    "plot",
                    path,
                    "--chart",
                    chart,
                    "--group",
                    "daily",
                    "--from",
                    "2026-06-01",
                    "--to",
                    "2026-06-30",
                    "--width",
                    "70",
                )
                self.assertEqual(0, code, err)
                for token in expected:
                    self.assertIn(token, out)

    def test_task_grouping_daily_weekly_and_monthly(self):
        path = self._make_file(
            "[x] T A done:2026-06-01\n"
            "[x] T B done:2026-06-07\n"
            "[x] T C done:2026-06-08\n"
        )
        cases = (
            ("daily", ("2026-06-01", "2026-06-07", "2026-06-08")),
            ("weekly", ("2026-W23", "2026-W24")),
            ("monthly", ("2026-06",)),
        )
        for group, expected in cases:
            with self.subTest(group=group):
                code, out, err = self._run(
                    "plot",
                    path,
                    "--chart",
                    "tasks",
                    "--group",
                    group,
                    "--from",
                    "2026-06-01",
                    "--to",
                    "2026-06-30",
                    "--width",
                    "70",
                )
                self.assertEqual(0, code, err)
                for token in expected:
                    self.assertIn(token, out)

        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "tasks",
            "--group",
            "weekly",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--width",
            "70",
        )
        self.assertEqual(0, code, err)
        week_23 = next(line for line in out.splitlines() if "2026-W23" in line)
        week_24 = next(line for line in out.splitlines() if "2026-W24" in line)
        self.assertTrue(week_23.rstrip().endswith("2"))
        self.assertTrue(week_24.rstrip().endswith("1"))

    def test_range_is_inclusive_at_both_boundaries(self):
        path = self._make_file(
            "[x] T Start done:2026-06-01\n"
            "[x] T Middle done:2026-06-15\n"
            "[x] T End done:2026-06-30\n"
        )
        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "tasks",
            "--group",
            "daily",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--width",
            "70",
        )
        self.assertEqual(0, code, err)
        self.assertIn("2026-06-01", out)
        self.assertIn("2026-06-15", out)
        self.assertIn("2026-06-30", out)

    def test_project_filter_applies_before_all_chart_families(self):
        path = self._make_file()
        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "all",
            "--project",
            "alpha",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--width",
            "70",
        )
        self.assertEqual(0, code, err)
        self.assertIn("happy", out)
        self.assertNotIn("calm", out)
        self.assertIn("alpha", out)
        self.assertNotIn("beta", out)

    def test_text_and_sparkline_outputs_are_deterministic_for_data_and_empty_input(self):
        path = self._make_file("[x] T A done:2026-06-01\n[x] T B done:2026-06-08\n")
        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "tasks",
            "--group",
            "weekly",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--width",
            "50",
            "--sparkline",
        )
        self.assertEqual(0, code, err)
        self.assertIn("## Tasks Completed (weekly)", out)
        self.assertIn("## Sparklines", out)
        self.assertIn("Tasks:", out)
        self.assertNotIn("(empty)", out)

        empty = self._make_file("")
        code, out, err = self._run(
            "plot",
            empty,
            "--chart",
            "tasks",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--width",
            "50",
            "--sparkline",
        )
        self.assertEqual(0, code, err)
        self.assertIn("## Sparklines", out)
        self.assertIn("Tasks:     (empty)", out)

    def test_empty_svg_is_valid_and_reports_no_plot_data(self):
        path = self._make_file("")
        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "tasks",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--format",
            "svg",
        )
        self.assertEqual(0, code, err)
        self.assertIn('<svg xmlns="http://www.w3.org/2000/svg"', out)
        self.assertIn("No plot data.", out)

    def test_svg_output_can_be_written_to_a_file(self):
        path = self._make_file("[x] T Done done:2026-06-10\n")
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "plot.svg")
            code, out, err = self._run(
                "plot",
                path,
                "--chart",
                "tasks",
                "--from",
                "2026-06-01",
                "--to",
                "2026-06-30",
                "--format",
                "svg",
                "-o",
                output,
            )
            self.assertEqual(0, code, err)
            self.assertEqual("", out)
            with open(output, encoding="utf-8") as handle:
                svg = handle.read()
        self.assertIn("<svg", svg)
        self.assertIn("Tasks Completed (weekly)", svg)

    def test_png_requires_output_path_at_the_command_boundary(self):
        path = self._make_file("[x] T Done done:2026-06-10\n")
        code, out, err = self._run(
            "plot",
            path,
            "--chart",
            "tasks",
            "--from",
            "2026-06-01",
            "--to",
            "2026-06-30",
            "--format",
            "png",
        )
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertEqual("ERROR: --format png requires -o/--output.\n", err)

    def test_png_command_delegates_rendering_with_semantic_plot_data(self):
        path = self._make_file("[x] T Done done:2026-06-10\n")
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "plot.png")
            with mock.patch.object(cli, "_plot_data_to_png") as renderer:
                code, out, err = self._run(
                    "plot",
                    path,
                    "--chart",
                    "tasks",
                    "--group",
                    "daily",
                    "--from",
                    "2026-06-01",
                    "--to",
                    "2026-06-30",
                    "--format",
                    "png",
                    "-o",
                    output,
                )

        self.assertEqual(0, code, err)
        self.assertEqual("", out)
        renderer.assert_called_once()
        plot_data, output_path = renderer.call_args.args
        self.assertEqual(output, output_path)
        self.assertEqual(
            {"2026-06-10": 1},
            dict(plot_data["Tasks Completed (daily)"]),
        )
