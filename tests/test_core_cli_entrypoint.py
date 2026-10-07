"""Focused regression tests for Core CLI entrypoint and legacy dispatch (#1132).

These tests intentionally stop at routing boundaries. They verify global option
extraction, selector translation, delegate choice, and CLI error normalization
without starting servers, opening browsers, performing network calls, or
mutating user files. Command semantics remain covered by their existing feature
tests.
"""

import argparse
import contextlib
import datetime
import io
import sys
import types
import unittest
from unittest import mock

import lifetxt
from lifetxt import entrypoint


def _module_with_main(name, *, return_value=0, side_effect=None):
    module = types.ModuleType(name)
    delegate = mock.Mock(return_value=return_value, side_effect=side_effect)
    module.main = delegate
    return module, delegate


class CoreCliEntrypointDispatchTests(unittest.TestCase):
    def test_public_main_bootstraps_then_dispatches(self):
        with (
            mock.patch.object(lifetxt, "bootstrap_legacy_surfaces") as bootstrap,
            mock.patch.object(entrypoint, "_dispatch", return_value=17) as dispatch,
        ):
            result = entrypoint.main(["today"])

        self.assertEqual(17, result)
        bootstrap.assert_called_once_with()
        dispatch.assert_called_once_with(["today"])

    def test_global_options_forward_split_config_and_equals_workspace(self):
        module, delegate = _module_with_main("lifetxt.extra_cli", return_value=21)
        with mock.patch.dict(sys.modules, {"lifetxt.extra_cli": module}):
            result = entrypoint._dispatch(
                ["next", "--config", "alpha.json", "--workspace=home"]
            )

        self.assertEqual(21, result)
        delegate.assert_called_once_with(
            ["next"], config_path="alpha.json", workspace_name="home"
        )

    def test_global_options_forward_equals_config_and_split_workspace(self):
        module, delegate = _module_with_main(
            "lifetxt.personal_context_cli", return_value=22
        )
        with mock.patch.dict(sys.modules, {"lifetxt.personal_context_cli": module}):
            result = entrypoint._dispatch(
                ["context", "health", "--config=beta.json", "--workspace", "work"]
            )

        self.assertEqual(22, result)
        delegate.assert_called_once_with(
            ["context", "health"], config_path="beta.json", workspace_name="work"
        )

    def test_missing_global_option_values_use_cli_error_contract(self):
        cases = (
            (["next", "--config"], "ERROR: --config requires a path.\n"),
            (["next", "--workspace"], "ERROR: --workspace requires a name.\n"),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                error = io.StringIO()
                with contextlib.redirect_stderr(error):
                    result = entrypoint._dispatch(argv)
                self.assertEqual(1, result)
                self.assertEqual(expected, error.getvalue())

    def test_review_implicit_year_uses_supplied_today(self):
        today = datetime.date(2026, 7, 20)
        self.assertEqual(
            [
                "review",
                "--from",
                "2026-01-01",
                "--to",
                "2026-12-31",
            ],
            entrypoint._review_selector_args(["review", "--year"], today),
        )

    def test_review_invalid_year_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "--year accepts a four-digit year"):
            entrypoint._review_selector_args(
                ["review", "--year", "20x6"], datetime.date(2026, 7, 20)
            )

    def test_review_selector_conflicts_are_rejected(self):
        today = datetime.date(2026, 7, 20)
        cases = (
            (
                ["review", "--last-week", "--last-month"],
                "Use only one of --last-week, --last-month, or --year.",
            ),
            (
                ["review", "--last-week", "--week", "2026-W29"],
                "Convenience review selectors cannot be combined",
            ),
            (
                ["review", "--year", "--from", "2026-01-01"],
                "Convenience review selectors cannot be combined",
            ),
        )
        for argv, message in cases:
            with self.subTest(argv=argv):
                with self.assertRaisesRegex(ValueError, message):
                    entrypoint._review_selector_args(argv, today)

    def test_review_dispatch_translates_and_forwards_globals(self):
        legacy = mock.Mock(return_value=23)
        with (
            mock.patch.object(
                entrypoint,
                "timezone_today",
                return_value=datetime.date(2026, 7, 20),
            ),
            mock.patch.object(entrypoint, "_legacy_main", legacy),
        ):
            result = entrypoint._dispatch(
                [
                    "review",
                    "--last-week",
                    "--config=review.json",
                    "--workspace",
                    "journal",
                ]
            )

        self.assertEqual(23, result)
        legacy.assert_called_once_with(
            [
                "review",
                "--from",
                "2026-07-13",
                "--to",
                "2026-07-19",
                "--config",
                "review.json",
                "--workspace",
                "journal",
            ]
        )

    def test_legacy_fallback_is_separate_from_intercepted_routes(self):
        taxonomy = types.ModuleType("lifetxt.cli_taxonomy")
        taxonomy.all_command_tokens = mock.Mock(return_value={"today"})
        legacy = mock.Mock(return_value=24)
        with (
            mock.patch.dict(sys.modules, {"lifetxt.cli_taxonomy": taxonomy}),
            mock.patch.object(lifetxt, "cli_taxonomy", taxonomy, create=True),
            mock.patch.object(entrypoint, "_legacy_main", legacy),
        ):
            result = entrypoint._dispatch(["today", "--config=core.json"])

        self.assertEqual(24, result)
        legacy.assert_called_once_with(["today", "--config=core.json"])

    def test_report_route_forwards_global_options(self):
        module, delegate = _module_with_main("lifetxt.report_cli", return_value=25)
        with mock.patch.dict(sys.modules, {"lifetxt.report_cli": module}):
            result = entrypoint._dispatch(
                [
                    "report",
                    "preview",
                    "weekly",
                    "--config",
                    "report.json",
                    "--workspace=team",
                ]
            )

        self.assertEqual(25, result)
        delegate.assert_called_once_with(
            ["report", "preview", "weekly"],
            config_path="report.json",
            workspace_name="team",
        )

    def test_server_report_and_git_commit_worker_routes(self):
        cases = (
            (
                "lifetxt.server_report_cli",
                ["server-report", "plan", "--app-config", "server.json"],
                26,
            ),
            (
                "lifetxt.git_commit_worker_cli",
                ["git-commit-worker", "run", "--once"],
                27,
            ),
        )
        for module_name, argv, return_value in cases:
            with self.subTest(module_name=module_name):
                module, delegate = _module_with_main(
                    module_name, return_value=return_value
                )
                with mock.patch.dict(sys.modules, {module_name: module}):
                    result = entrypoint._dispatch(argv)

                self.assertEqual(return_value, result)
                delegate.assert_called_once_with(argv)

    def test_special_extra_routes_delegate_without_side_effects(self):
        cases = (
            (
                [
                    "import-ics",
                    "calendar.ics",
                    "--preset",
                    "todo",
                    "--output",
                    "life.txt",
                ],
                ["from-todo", "calendar.ics", "--output", "life.txt"],
            ),
            (
                [
                    "files",
                    "--open",
                    "item-1",
                    "--config",
                    "files.json",
                    "--workspace=home",
                ],
                ["files", "--open", "item-1"],
            ),
            (["who", "--workload"], ["who", "--workload"]),
            (["quick", "--journal"], ["quick", "--journal"]),
            (["completion", "powershell"], ["completion", "powershell"]),
            (
                ["doctor", "--workspace-safety"],
                ["doctor", "--workspace-safety"],
            ),
        )
        for argv, expected_argv in cases:
            with self.subTest(argv=argv):
                module, delegate = _module_with_main(
                    "lifetxt.extra_cli", return_value=28
                )
                with mock.patch.dict(sys.modules, {"lifetxt.extra_cli": module}):
                    result = entrypoint._dispatch(argv)

                self.assertEqual(28, result)
                expected_config = "files.json" if argv[0] == "files" else None
                expected_workspace = "home" if argv[0] == "files" else None
                delegate.assert_called_once_with(
                    expected_argv,
                    config_path=expected_config,
                    workspace_name=expected_workspace,
                )

    def test_intercepted_value_and_os_errors_are_normalized(self):
        cases = (
            (ValueError("invalid routed input"), "ERROR: invalid routed input\n"),
            (OSError("routed read failed"), "ERROR: routed read failed\n"),
        )
        for exc, expected in cases:
            with self.subTest(exception=type(exc).__name__):
                module, _delegate = _module_with_main(
                    "lifetxt.extra_cli", side_effect=exc
                )
                error = io.StringIO()
                with (
                    mock.patch.dict(sys.modules, {"lifetxt.extra_cli": module}),
                    contextlib.redirect_stderr(error),
                ):
                    result = entrypoint._dispatch(["next"])

                self.assertEqual(1, result)
                self.assertEqual(expected, error.getvalue())

    def test_unknown_command_remains_exit_two(self):
        taxonomy = types.ModuleType("lifetxt.cli_taxonomy")
        taxonomy.all_command_tokens = mock.Mock(return_value={"today", "check"})
        error = io.StringIO()
        with (
            mock.patch.dict(sys.modules, {"lifetxt.cli_taxonomy": taxonomy}),
            mock.patch.object(lifetxt, "cli_taxonomy", taxonomy, create=True),
            contextlib.redirect_stderr(error),
        ):
            result = entrypoint._dispatch(["definitely-not-a-command"])

        self.assertEqual(2, result)
        self.assertEqual(
            "ERROR: Unknown command: 'definitely-not-a-command'\n",
            error.getvalue(),
        )


class LegacyCliCommonMainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from lifetxt import cli

        cls.cli = cli

    def test_missing_config_and_workspace_values_preserve_exit_one(self):
        cases = (
            (["today", "--config"], "ERROR: --config requires a path.\n"),
            (["today", "--workspace"], "ERROR: --workspace requires a name.\n"),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                error = io.StringIO()
                with contextlib.redirect_stderr(error):
                    result = self.cli.main(argv)
                self.assertEqual(1, result)
                self.assertEqual(expected, error.getvalue())

    def test_config_load_failure_is_normalized_before_command_execution(self):
        parser = mock.Mock()
        command = mock.Mock(return_value=0)
        parser.parse_args.return_value = argparse.Namespace(func=command)
        error = io.StringIO()
        with (
            mock.patch.object(self.cli, "build_parser", return_value=parser),
            mock.patch.object(
                self.cli,
                "load_config",
                side_effect=ValueError("Could not read config: broken.json"),
            ),
            contextlib.redirect_stderr(error),
        ):
            result = self.cli.main(["today", "--config", "broken.json"])

        self.assertEqual(1, result)
        self.assertEqual("ERROR: Could not read config: broken.json\n", error.getvalue())
        command.assert_not_called()

    def test_workspace_resolution_failure_is_normalized_before_command_execution(self):
        parser = mock.Mock()
        command = mock.Mock(return_value=0)
        parser.parse_args.return_value = argparse.Namespace(func=command)
        error = io.StringIO()
        with (
            mock.patch.object(self.cli, "build_parser", return_value=parser),
            mock.patch.object(self.cli, "load_config", return_value={}),
            mock.patch.object(
                self.cli,
                "_maybe_apply_workspace",
                side_effect=ValueError(
                    "Unknown workspace 'missing'. Available: (none)"
                ),
            ),
            contextlib.redirect_stderr(error),
        ):
            result = self.cli.main(["today", "--workspace", "missing"])

        self.assertEqual(1, result)
        self.assertEqual(
            "ERROR: Unknown workspace 'missing'. Available: (none)\n",
            error.getvalue(),
        )
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
