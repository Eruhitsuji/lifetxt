"""Core invocation contracts; feature handlers are deliberately not executed."""

import contextlib
import datetime
import io
import itertools
import sys
import unittest
from unittest import mock

from lifetxt import bootstrap_legacy_surfaces, cli, entrypoint


class CliContractTestCase(unittest.TestCase):
    def setUp(self):
        bootstrap_legacy_surfaces()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stdout = self.stack.enter_context(
            contextlib.redirect_stdout(io.StringIO())
        )
        self.stderr = self.stack.enter_context(
            contextlib.redirect_stderr(io.StringIO())
        )
        self.stack.enter_context(mock.patch.dict("os.environ", {"LIFETXT_LANG": "en"}))
        # A previously installed timezone wrapper captures load_config itself.
        # Isolate its path lookup too, so it cannot read real configuration.
        self.stack.enter_context(
            mock.patch("lifetxt.config.find_config_path", return_value=None)
        )
        self.stack.enter_context(
            mock.patch(
                "lifetxt.timezone_policy.cli_timezone_candidate_paths", return_value=[]
            )
        )

    def assert_error(self, result, message, code=1):
        self.assertEqual(result, code)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "ERROR: " + message + "\n")


class EntrypointDispatchTests(CliContractTestCase):
    def setUp(self):
        super().setUp()
        self.delegates = {
            name: self.stack.enter_context(mock.patch(target, return_value=7))
            for name, target in (
                ("legacy", "lifetxt.entrypoint._legacy_main"),
                ("extra", "lifetxt.extra_cli.main"),
                ("report", "lifetxt.report_cli.main"),
                ("server-report", "lifetxt.server_report_cli.main"),
                ("worker", "lifetxt.git_commit_worker_cli.main"),
                ("context", "lifetxt.personal_context_cli.main"),
            )
        }

    def assert_route(self, argv, delegate, forwarded, **kwargs):
        for handler in self.delegates.values():
            handler.reset_mock()
        original = list(argv)
        self.assertEqual(entrypoint.main(argv), 7)
        self.delegates[delegate].assert_called_once_with(forwarded, **kwargs)
        for name, handler in self.delegates.items():
            if name != delegate:
                handler.assert_not_called()
        self.assertEqual(argv, original)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")

    def test_intercepted_families_strip_and_forward_global_options(self):
        routes = (
            (["next", "--why"], "extra"),
            (["report", "preview", "weekly"], "report"),
            (
                ["server-report", "plan", "weekly", "--app-config", "app.json"],
                "server-report",
            ),
            (["git-commit-worker", "--help"], "worker"),
            (["context", "health"], "context"),
        )
        forms = (
            ["--config", "config with spaces.json", "--workspace", "research"],
            ["--config=config with spaces.json", "--workspace=research"],
        )
        for (command, delegate), options, placement in itertools.product(
            routes, forms, ("before", "after")
        ):
            with self.subTest(command=command, options=options, placement=placement):
                argv = options + command if placement == "before" else command + options
                kwargs = (
                    {}
                    if delegate in ("server-report", "worker")
                    else {
                        "config_path": "config with spaces.json",
                        "workspace_name": "research",
                    }
                )
                self.assert_route(argv, delegate, command, **kwargs)

    def test_personal_context_command_family(self):
        for command in (
            "context",
            "memory",
            "decisions",
            "decision-review",
            "change-feed",
            "future-intent",
        ):
            with self.subTest(command=command):
                self.assert_route(
                    [command, "--help"],
                    "context",
                    [command, "--help"],
                    config_path=None,
                    workspace_name=None,
                )

    def test_special_extra_routes(self):
        routes = (
            (
                ["import-ics", "input.ics", "--preset", "todo", "--dry-run"],
                ["from-todo", "input.ics", "--dry-run"],
            ),
            (["review", "--someday"], ["review", "--someday"]),
            (["files", "--open", "t1"], ["files", "--open", "t1"]),
            (["who", "--workload"], ["who", "--workload"]),
            (["quick", "--journal", "A note"], ["quick", "--journal", "A note"]),
            (["completion", "powershell"], ["completion", "powershell"]),
            (
                ["completion", "install", "--shell", "powershell"],
                ["completion", "install", "--shell", "powershell"],
            ),
        )
        for command, forwarded in routes:
            with self.subTest(command=command):
                self.assert_route(
                    command + ["--config=c.json", "--workspace=w"],
                    "extra",
                    forwarded,
                    config_path="c.json",
                    workspace_name="w",
                )

    def test_doctor_safety_flags_in_split_and_equals_forms(self):
        for flag in (
            "--workspace-safety",
            "--archive",
            "--timer-state",
            "--revision-metrics",
            "--cleanup-stale",
            "--fold-policy",
            "--gap-policy",
        ):
            for option in (flag, flag + "=value"):
                with self.subTest(option=option):
                    command = ["doctor", "--format", "json", option]
                    self.assert_route(
                        command + ["--config", "c.json", "--workspace", "w"],
                        "extra",
                        command,
                        config_path="c.json",
                        workspace_name="w",
                    )

    def test_legacy_routes_preserve_original_arguments(self):
        commands = (
            ["check", "input.txt"],
            ["review", "--week"],
            ["files"],
            ["who"],
            ["quick", "A task"],
            ["completion", "bash"],
            ["doctor"],
            ["import-ics", "input.ics", "--preset", "calendar"],
            ["import-ics", "input.ics", "--preset"],
            ["--version"],
        )
        for command in commands:
            with self.subTest(command=command):
                argv = ["--config", "c.json"] + command + ["--workspace=w"]
                self.assert_route(argv, "legacy", argv)

    def test_sys_argv_is_used_when_argument_is_omitted(self):
        argv = ["--config=c.json", "next", "--workspace=w"]
        with mock.patch.object(sys, "argv", ["lifetxt"] + argv):
            self.assertEqual(entrypoint.main(), 7)
        self.delegates["extra"].assert_called_once_with(
            ["next"], config_path="c.json", workspace_name="w"
        )

    def test_language_override_is_removed_before_routing(self):
        for option in (["--lang", "en"], ["--lang=en"]):
            with self.subTest(option=option):
                self.assert_route(
                    option + ["next", "--config=c.json"],
                    "extra",
                    ["next"],
                    config_path="c.json",
                    workspace_name=None,
                )

    def test_missing_language_value_stops_before_routing(self):
        self.assert_error(
            entrypoint.main(["next", "--lang"]), "--lang requires a value."
        )
        for delegate in self.delegates.values():
            delegate.assert_not_called()

    def test_empty_noninteractive_and_global_only_invocations_use_legacy(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False):
            for argv in ([], ["--config=c.json"], ["--workspace", "w"]):
                with self.subTest(argv=argv):
                    self.assert_route(argv, "legacy", argv)

    def test_missing_global_values_stop_before_delegation(self):
        for option, message in (
            ("--config", "--config requires a path."),
            ("--workspace", "--workspace requires a name."),
        ):
            with self.subTest(option=option):
                self.stderr.seek(0)
                self.stderr.truncate()
                self.assert_error(entrypoint.main(["next", option]), message)
                for delegate in self.delegates.values():
                    delegate.assert_not_called()

    def test_unknown_command_keeps_exit_two_and_stderr_only(self):
        self.assert_error(
            entrypoint.main(["no-such-command"]),
            "Unknown command: 'no-such-command'",
            code=2,
        )
        for delegate in self.delegates.values():
            delegate.assert_not_called()

    def test_intercepted_value_and_os_errors_are_normalized(self):
        for exception in (
            ValueError("Invalid report profile."),
            OSError("Cannot read input."),
        ):
            with self.subTest(exception=type(exception).__name__):
                self.stderr.seek(0)
                self.stderr.truncate()
                self.delegates["report"].side_effect = exception
                self.assert_error(
                    entrypoint.main(["report", "preview", "weekly"]), str(exception)
                )
        self.delegates["legacy"].assert_not_called()

    def test_review_selectors_translate_with_fixed_date_and_forward_globals(self):
        cases = (
            (["--last-week"], ["--from", "2025-12-22", "--to", "2025-12-28"]),
            (["--last-month"], ["--month", "2025-12"]),
            (["--year"], ["--from", "2026-01-01", "--to", "2026-12-31"]),
            (["--year", "2024"], ["--from", "2024-01-01", "--to", "2024-12-31"]),
            (
                ["--year", "--format", "json"],
                ["--format", "json", "--from", "2026-01-01", "--to", "2026-12-31"],
            ),
        )
        with mock.patch.object(
            entrypoint, "timezone_today", return_value=datetime.date(2026, 1, 1)
        ):
            for selector, translated in cases:
                for options in (
                    [],
                    ["--config=c.json"],
                    ["--workspace=w"],
                    ["--config", "c.json", "--workspace", "w"],
                ):
                    with self.subTest(selector=selector, options=options):
                        forwarded = ["review"] + translated
                        if any(value.startswith("--config") for value in options):
                            forwarded += ["--config", "c.json"]
                        if any(value.startswith("--workspace") for value in options):
                            forwarded += ["--workspace", "w"]
                        self.assert_route(
                            ["review"] + selector + options, "legacy", forwarded
                        )

    def test_invalid_review_year_stops_dispatch(self):
        for year in ("20", "20260", "abcd"):
            with self.subTest(year=year):
                self.stderr.seek(0)
                self.stderr.truncate()
                with mock.patch.object(
                    entrypoint, "timezone_today", return_value=datetime.date(2026, 1, 1)
                ):
                    self.assert_error(
                        entrypoint.main(["review", "--year", year]),
                        "--year accepts a four-digit year.",
                    )
                for delegate in self.delegates.values():
                    delegate.assert_not_called()

    def test_review_selector_conflicts_stop_dispatch(self):
        selectors = ("--last-week", "--last-month", "--year")
        conflicts = [
            (list(pair), "Use only one of --last-week, --last-month, or --year.")
            for pair in itertools.combinations(selectors, 2)
        ]
        conflicts += [
            (
                [selector, legacy],
                "Convenience review selectors cannot be combined with --week, --month, --from, or --to.",
            )
            for selector, legacy in itertools.product(
                selectors, ("--week", "--month", "--from", "--to")
            )
        ]
        with mock.patch.object(
            entrypoint, "timezone_today", return_value=datetime.date(2026, 1, 1)
        ):
            for flags, message in conflicts:
                with self.subTest(flags=flags):
                    self.stderr.seek(0)
                    self.stderr.truncate()
                    self.assert_error(entrypoint.main(["review"] + flags), message)
                    for delegate in self.delegates.values():
                        delegate.assert_not_called()


class LegacyMainContractTests(CliContractTestCase):
    def setUp(self):
        super().setUp()
        self.load_config = self.stack.enter_context(
            mock.patch.object(cli, "load_config", return_value={})
        )
        self.handler = self.stack.enter_context(
            mock.patch.object(cli, "command_check", return_value=7)
        )

    def test_entrypoint_legacy_bridge_calls_cli_main_with_raw_arguments(self):
        argv = ["--config=c.json", "check", "input.txt", "--workspace", "w"]
        # The bridge installs an idempotent wrapper; isolate that installer so
        # the public delegate remains the mock rather than a wrapper of it.
        with (
            mock.patch("lifetxt.runtime_safety_v2.install_cli_timezone_context"),
            mock.patch.object(cli, "main", return_value=7) as delegate,
        ):
            self.assertEqual(entrypoint.main(argv), 7)
        delegate.assert_called_once_with(argv)
        self.handler.assert_not_called()

    def test_global_options_reach_legacy_handler_namespace(self):
        forms = (
            ["--config", "c.json", "--workspace", "w"],
            ["--config=c.json", "--workspace=w"],
        )
        for options, placement in itertools.product(forms, ("before", "after")):
            with self.subTest(options=options, placement=placement):
                self.handler.reset_mock()
                self.load_config.reset_mock()
                argv = (
                    options + ["check", "input.txt"]
                    if placement == "before"
                    else ["check", "input.txt"] + options
                )
                self.assertEqual(cli.main(argv), 7)
                self.load_config.assert_called_once_with("c.json")
                self.handler.assert_called_once()
                args = self.handler.call_args.args[0]
                self.assertEqual(
                    (args.config, args.workspace, args.paths, args.config_data),
                    ("c.json", "w", ["input.txt"], {}),
                )
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertEqual(self.stderr.getvalue(), "")

    def test_legacy_sys_argv_when_argument_is_omitted(self):
        with mock.patch.object(
            sys, "argv", ["lifetxt", "check", "input.txt", "--config=c.json"]
        ):
            self.assertEqual(cli.main(), 7)
        self.load_config.assert_called_once_with("c.json")
        self.handler.assert_called_once()
        self.assertEqual(self.handler.call_args.args[0].paths, ["input.txt"])

    def test_missing_global_values_do_not_load_config_or_run_handler(self):
        for option, message in (
            ("--config", "--config requires a path."),
            ("--workspace", "--workspace requires a name."),
        ):
            with self.subTest(option=option):
                self.stderr.seek(0)
                self.stderr.truncate()
                self.assert_error(cli.main(["check", option]), message)
                self.load_config.assert_not_called()
                self.handler.assert_not_called()

    def test_config_failure_stops_before_workspace_and_handler(self):
        self.load_config.side_effect = ValueError(
            "Could not read config: c.json\nReason: invalid JSON"
        )
        with mock.patch.object(cli, "_maybe_apply_workspace") as workspace:
            self.assert_error(
                cli.main(["check", "--config=c.json"]),
                "Could not read config: c.json\nReason: invalid JSON",
            )
        workspace.assert_not_called()
        self.handler.assert_not_called()

    def test_unknown_workspace_preserves_error_contract(self):
        self.load_config.return_value = {
            "workspaces": {"research": {"paths": ["input.txt"]}}
        }
        self.assert_error(
            cli.main(["check", "--workspace=missing"]),
            "Unknown workspace 'missing'. Available: research",
        )
        self.handler.assert_not_called()

    def test_handler_value_error_is_normalized(self):
        self.handler.side_effect = ValueError("Invalid check input.")
        self.assert_error(cli.main(["check"]), "Invalid check input.")
        self.handler.assert_called_once()

    def test_no_subcommand_prints_help_and_returns_two(self):
        self.assertEqual(cli.main([]), 2)
        self.assertIn("usage: python -m lifetxt", self.stdout.getvalue())
        self.assertEqual(self.stderr.getvalue(), "")
        self.handler.assert_not_called()

    def test_invalid_legacy_arguments_preserve_argparse_exit_two(self):
        with self.assertRaises(SystemExit) as raised:
            cli.main(["check", "--no-such-option"])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(self.stdout.getvalue(), "")
        self.assertIn(
            "unrecognized arguments: --no-such-option", self.stderr.getvalue()
        )
        self.load_config.assert_not_called()
        self.handler.assert_not_called()

    def test_fzf_preview_delegates_token_without_config_loading(self):
        with mock.patch(
            "lifetxt.fzf_helper.cmd_fzf_preview", return_value=7
        ) as preview:
            self.assertEqual(cli.main(["fzf-preview", "opaque-token"]), 7)
        preview.assert_called_once()
        self.assertEqual(preview.call_args.args[0].token, "opaque-token")
        self.load_config.assert_not_called()
        self.handler.assert_not_called()

    def test_fzf_preview_wrong_arity_returns_two(self):
        for args in (["fzf-preview"], ["fzf-preview", "one", "two"]):
            with self.subTest(args=args):
                self.stderr.seek(0)
                self.stderr.truncate()
                self.assert_error(
                    cli.main(args), "fzf-preview requires one token.", code=2
                )
                self.load_config.assert_not_called()
                self.handler.assert_not_called()
