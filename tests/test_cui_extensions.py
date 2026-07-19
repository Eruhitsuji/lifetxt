import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from unittest.mock import patch

from lifetxt import cli, completion, fzf_helper, git_hook, stats, timer, tui, tui_app
from lifetxt.interactive import DETAIL_DESCRIPTIONS, detail_candidates
from lifetxt.parser import parse_text


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CompletionTests(unittest.TestCase):
    def test_generates_completion_for_new_commands(self):
        script = completion.bash_completion()

        self.assertIn("sources", script)
        self.assertIn("timer", script)
        self.assertIn("stats", script)
        self.assertIn("git-hook", script)
        self.assertIn("--type", script)
        self.assertIn("--body-file", script)
        self.assertIn("--body-stdin", script)
        self.assertIn("--rrule", script)
        self.assertIn("--notify-at", script)
        self.assertIn("--occurrences", script)
        self.assertIn("--theme", script)
        self.assertIn("--keymap", script)
        self.assertIn("auto dark light mono", script)
        self.assertIn("vim arrows", script)

    def test_prints_fish_install_instructions(self):
        text = completion.install_instructions("fish")

        self.assertIn("lifetxt.fish", text)
        self.assertIn("lifetxt completion fish", text)

    def test_interactive_detail_candidates_include_multiline_body(self):
        self.assertIn("body<<", detail_candidates("J"))
        self.assertIn("elapsed", DETAIL_DESCRIPTIONS)

    def test_completion_commands_match_argparse_subcommands(self):
        parser = cli.build_parser()
        commands = _subcommand_names(parser)

        self.assertEqual(commands, completion._command_names())

    def test_completion_options_cover_argparse_long_options(self):
        parser = cli.build_parser()
        expected = _long_options(parser)
        actual = set(completion._all_options())

        self.assertEqual([], sorted(expected - actual))


class CliParserConsistencyTests(unittest.TestCase):
    def test_filter_based_commands_share_item_filter_options(self):
        parser = cli.build_parser()
        expected = {
            "--open",
            "--status",
            "--type",
            "--project",
            "--tag",
            "--tag-all",
            "--exclude-tag",
            "--user",
            "--team",
            "--person",
            "--owner",
            "--assignee",
            "--attendee",
            "--sender",
            "--recipient",
            "--detail",
            "--text",
            "--after",
            "--before",
        }
        for command in ("filter", "agenda", "stats", "to-json", "to-jsonl", "to-csv", "markdown"):
            subparser = _subparser(parser, command)
            options = {
                option
                for action in subparser._actions
                for option in action.option_strings
            }
            missing = sorted(expected - options)
            self.assertEqual([], missing, command)


def _subparser(parser, name):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError("parser has no subcommands")


def _subcommand_names(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return tuple(action.choices.keys())
    raise AssertionError("parser has no subcommands")


def _long_options(parser):
    options = set()

    def walk(arg_parser):
        for action in arg_parser._actions:
            for option in action.option_strings:
                if option.startswith("--"):
                    options.add(option)
            if isinstance(action, argparse._SubParsersAction):
                for subparser in action.choices.values():
                    walk(subparser)

    walk(parser)
    return options


class GitHookTests(unittest.TestCase):
    def test_install_and_uninstall_lifetxt_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = os.path.join(tmp, ".git", "hooks")
            os.makedirs(hooks_dir)
            args = argparse.Namespace(
                repo_dir=tmp,
                files=["life.txt"],
                no_commit_msg=False,
                force=False,
                config_data={},
            )

            with redirect_stdout(io.StringIO()):
                git_hook.install_hooks(args)

            pre_commit = os.path.join(hooks_dir, "pre-commit")
            commit_msg = os.path.join(hooks_dir, "commit-msg")
            self.assertTrue(os.path.exists(pre_commit))
            self.assertTrue(os.path.exists(commit_msg))
            with open(pre_commit, "r", encoding="utf-8") as handle:
                self.assertIn(git_hook.MARKER, handle.read())

            with redirect_stdout(io.StringIO()):
                git_hook.uninstall_hooks(argparse.Namespace(repo_dir=tmp))

            self.assertFalse(os.path.exists(pre_commit))
            self.assertFalse(os.path.exists(commit_msg))

    def test_install_refuses_non_lifetxt_hook_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            hooks_dir = os.path.join(tmp, ".git", "hooks")
            os.makedirs(hooks_dir)
            with open(os.path.join(hooks_dir, "pre-commit"), "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\necho custom\n")
            args = argparse.Namespace(
                repo_dir=tmp,
                files=["life.txt"],
                no_commit_msg=True,
                force=False,
                config_data={},
            )

            with self.assertRaises(ValueError):
                git_hook.install_hooks(args)


class TimerTests(unittest.TestCase):
    def test_parse_and_format_elapsed(self):
        self.assertEqual(83, timer.parse_elapsed("1h23m"))
        self.assertEqual(60, timer.parse_elapsed("1h"))
        self.assertEqual("1h23m", timer.format_elapsed(83))

    def test_start_and_stop_timer_updates_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            state_file = os.path.join(tmp, "timer.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1 project:work\n")
            args = argparse.Namespace(
                path=path,
                item_id="t1",
                note=None,
                config_data={"timer": {"state_file": state_file}},
            )
            original_now = timer._now
            try:
                timer._now = lambda: datetime(2026, 6, 10, 10, 0, 0)
                with redirect_stdout(io.StringIO()):
                    timer.start_timer(args)

                with open(path, "r", encoding="utf-8") as handle:
                    self.assertIn("[/] T Write_Report", handle.read())
                with open(state_file, "r", encoding="utf-8") as handle:
                    state = json.load(handle)
                self.assertEqual("t1", state["id"])

                timer._now = lambda: datetime(2026, 6, 10, 11, 30, 0)
                with redirect_stdout(io.StringIO()):
                    timer.stop_timer(
                        argparse.Namespace(
                            path=None,
                            item_id=None,
                            config_data={"timer": {"state_file": state_file}},
                        )
                    )
            finally:
                timer._now = original_now

            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("elapsed:1h30m", text)
            self.assertFalse(os.path.exists(state_file))

    def test_pause_resume_timer_accumulates_elapsed_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            state_file = os.path.join(tmp, "timer.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Deep_Work id:t1 elapsed:10m\n")
            config_data = {"timer": {"state_file": state_file}}
            start_args = argparse.Namespace(
                path=path,
                item_id="t1",
                note=None,
                config_data=config_data,
            )
            command_args = argparse.Namespace(config_data=config_data)
            stop_args = argparse.Namespace(path=None, item_id=None, config_data=config_data)
            status_args = argparse.Namespace(paths=[path], config_data=config_data)
            original_now = timer._now
            try:
                timer._now = lambda: datetime(2026, 6, 10, 10, 0, 0)
                with redirect_stdout(io.StringIO()):
                    timer.start_timer(start_args)

                timer._now = lambda: datetime(2026, 6, 10, 10, 25, 0)
                with redirect_stdout(io.StringIO()):
                    timer.pause_timer(command_args)
                with open(state_file, "r", encoding="utf-8") as handle:
                    paused_state = json.load(handle)
                self.assertEqual(25, paused_state["accumulated_minutes"])
                self.assertEqual("2026-06-10T10:25:00", paused_state["paused_at"])

                output = io.StringIO()
                with redirect_stdout(output):
                    timer.status_timer(status_args)
                self.assertIn("Paused:", output.getvalue())
                self.assertIn("elapsed: 25m", output.getvalue())

                timer._now = lambda: datetime(2026, 6, 10, 11, 0, 0)
                with redirect_stdout(io.StringIO()):
                    timer.resume_timer(command_args)

                timer._now = lambda: datetime(2026, 6, 10, 11, 10, 0)
                with redirect_stdout(io.StringIO()):
                    timer.stop_timer(stop_args)
            finally:
                timer._now = original_now

            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("elapsed:45m", text)
            self.assertFalse(os.path.exists(state_file))

    def test_timer_cli_smoke_uses_real_state_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            state_file = os.path.join(tmp, "state", "timer.json")
            config_path = os.path.join(tmp, "lifetxt.config.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Smoke_Timer id:t1 project:work\n")
            with open(config_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump({"timer": {"state_file": state_file}}, handle)

            stdout, stderr, code = run_lifetxt_cli(
                "--config",
                config_path,
                "timer",
                "start",
                path,
                "--id",
                "t1",
            )
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Started timer for t1", stdout)
            self.assertTrue(os.path.exists(state_file))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertIn("[/] T Smoke_Timer", handle.read())

            stdout, stderr, code = run_lifetxt_cli(
                "--config",
                config_path,
                "timer",
                "status",
                path,
            )
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Running: t1", stdout)

            stdout, stderr, code = run_lifetxt_cli("--config", config_path, "timer", "pause")
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Paused timer for t1", stdout)
            with open(state_file, "r", encoding="utf-8") as handle:
                self.assertTrue(json.load(handle)["paused_at"])

            stdout, stderr, code = run_lifetxt_cli(
                "--config",
                config_path,
                "timer",
                "status",
                path,
            )
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Paused: t1", stdout)

            stdout, stderr, code = run_lifetxt_cli("--config", config_path, "timer", "resume")
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Resumed timer for t1", stdout)
            with open(state_file, "r", encoding="utf-8") as handle:
                self.assertEqual("", json.load(handle)["paused_at"])

            stdout, stderr, code = run_lifetxt_cli("--config", config_path, "timer", "stop")
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Stopped timer for t1", stdout)
            self.assertFalse(os.path.exists(state_file))
            with open(path, "r", encoding="utf-8") as handle:
                self.assertIn("elapsed:", handle.read())

            stdout, stderr, code = run_lifetxt_cli(
                "--config",
                config_path,
                "timer",
                "start",
                path,
                "--id",
                "t1",
            )
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertTrue(os.path.exists(state_file))

            stdout, stderr, code = run_lifetxt_cli("--config", config_path, "timer", "cancel")
            self.assertEqual("", stderr)
            self.assertEqual(0, code)
            self.assertIn("Canceled running timer.", stdout)
            self.assertFalse(os.path.exists(state_file))


class StatsTests(unittest.TestCase):
    def test_build_stats_for_tasks_habits_and_journals(self):
        text = (
            "[x] T Done_Task due:2026-06-10 project:work id:t1\n"
            "[ ] T Open_Task due:2026-06-09 project:work id:t2\n"
            "[N] J Day mood:good on:2026-06-10 id:j1\n"
            "[x] H Exercise repeat:daily done:2026-06-09 done:2026-06-10 id:h1\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            items = stats.load_items([path])
            data = stats.build_stats(
                items,
                stats._parse_date_only("2026-06-09"),
                stats._parse_date_only("2026-06-10"),
                "daily",
            )

        self.assertEqual(1, data["tasks"]["done"])
        self.assertEqual(2, data["tasks"]["total"])
        self.assertEqual(1, data["tasks"]["overdue"])
        self.assertEqual(1, data["journal_entries"])
        self.assertEqual(1, data["mood"]["counts"]["good"])
        self.assertEqual(2, data["habits"][0]["streak"])

    def test_weekly_stats_bucket_tasks_and_habits(self):
        text = (
            "[x] T Done_Task due:2026-06-02 project:work id:t1\n"
            "[ ] T Open_Task due:2026-06-09 project:work id:t2\n"
            "[x] H Exercise repeat:daily done:2026-06-02 done:2026-06-09 id:h1\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            items = stats.load_items([path])
            start = stats._parse_date_only("2026-06-01")
            end = stats._parse_date_only("2026-06-14")
            buckets = stats.make_buckets(start, end, "weekly")
            data = stats.build_stats(items, start, end, "weekly", buckets)

        self.assertEqual(2, len(data["tasks"]["buckets"]))
        self.assertEqual(1, data["tasks"]["buckets"][0]["done"])
        self.assertEqual(1, data["tasks"]["buckets"][1]["total"])
        self.assertEqual("==", data["habits"][0]["sparkline"])

    def test_progress_bar_is_ascii(self):
        bar = stats.progress_bar(50, width=4)

        self.assertEqual("[##..]", bar)


class FzfHelperTests(unittest.TestCase):
    def test_encode_and_decode_selection(self):
        items, diagnostics = parse_text("[ ] T Write_Report id:t1 body:hello\n")
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        items[0].source = "life.txt"

        line = fzf_helper.encode_item(items[0], "id")
        record = fzf_helper.decode_selection(line)

        self.assertEqual("t1", record["id"])
        self.assertEqual("life.txt", record["source"])
        self.assertIn("Write_Report", record["label"])
        self.assertIn("id:t1", line)

    def test_preview_token_formats_body_and_source(self):
        items, diagnostics = parse_text("[ ] T Write_Report id:t1\n| first line\n| second line\n")
        self.assertFalse(any(d.severity == "error" for d in diagnostics))
        items[0].source = "life.txt"

        token = fzf_helper.encode_item(items[0], "id").split("\t", 1)[0]
        preview = fzf_helper.preview_token(token)

        self.assertIn("source: life.txt:1", preview)
        self.assertIn("body:", preview)
        self.assertIn("first line", preview)
        self.assertIn("life.txt:", preview)

    def test_delete_requires_explicit_delete_confirmation(self):
        record = {
            "id": "t1",
            "source": "life.txt",
            "line": 1,
            "label": "[ ] T Write_Report",
            "body": "",
            "text": "[ ] T Write_Report id:t1",
        }
        args = argparse.Namespace(config_data={})
        original_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("y\n")
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                result = fzf_helper.run_action("delete", [record], args)
        finally:
            sys.stdin = original_stdin

        self.assertEqual(0, result)
        self.assertIn("Canceled.", stdout.getvalue())

    def test_update_item_marks_done_without_external_fzf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1\n")

            fzf_helper.update_item(path, "t1", "id", status="[x]")

            with open(path, "r", encoding="utf-8") as handle:
                self.assertIn("[x] T Write_Report", handle.read())


class TuiTests(unittest.TestCase):
    def test_render_dashboard_plain_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1\n")
            output = tui.render_dashboard(argparse.Namespace(paths=[path]), focus="tasks")

        self.assertIn("modern terminal workspace", output)
        self.assertIn("Cards: open:1", output)
        self.assertIn("> TASKS (open)", output)
        self.assertIn("Write_Report", output)
        self.assertIn("* [ ] T Write_Report", output)
        self.assertIn("INSPECTOR", output)

    def test_render_dashboard_help(self):
        output = tui.render_dashboard(argparse.Namespace(paths=[]), help_visible=True)

        self.assertIn("lifetxt TUI help", output)
        self.assertIn("tab / n", output)
        self.assertIn("h / left", output)
        self.assertIn("Enter/o", output)
        self.assertIn("/        search visible dashboard rows", output)

    def test_render_dashboard_uses_tui_config_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "[ ] T First id:t1 project:work\n"
                    "[ ] T Second id:t2 project:work\n"
                )
            output = tui.render_dashboard(
                argparse.Namespace(
                    paths=[path],
                    config_data={"tui": {"theme": "light", "keymap": "arrows", "limit": 1, "agenda_window": "6h"}},
                ),
                focus="tasks",
            )

        self.assertIn("Theme:light  Keymap:arrows  Limit:1  Window:6h", output)
        self.assertIn("First", output)
        self.assertNotIn("Second", output)

    def test_render_dashboard_search_filters_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "[ ] T Work_Task id:t1 project:work\n"
                    "[ ] T Home_Task id:t2 project:home\n"
                    "[/] S Focus from:2026-06-10T09:00 state:focus person:self\n"
                )
            args = argparse.Namespace(paths=[path], config_data={})
            output = tui.render_dashboard(args, search_query="home")

        self.assertIn("Search:home", output)
        self.assertIn("Home_Task", output)
        self.assertNotIn("Work_Task", output)
        self.assertNotIn("Focus", output)

    def test_tui_footer_supports_search_mode(self):
        footer = tui._footer_text("vim", search_query="work", search_editing=True)

        self.assertIn("search: work", footer)
        self.assertIn("Enter apply", footer)
        self.assertIn("Esc clear", footer)

    def test_render_dashboard_detail_and_action_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1 project:work\n| Body line\n")
            args = argparse.Namespace(paths=[path], config_data={})
            row = tui.selected_dashboard_row(args, 0)
            detail = tui.render_dashboard(args, detail_row=row)
            actions = tui.render_dashboard(args, action_row=row)

        self.assertIn("DETAIL", detail)
        self.assertIn("Body line", detail)
        self.assertIn("ACTIONS", actions)
        self.assertIn("d  mark done", actions)
        self.assertIn("f  filter by project:work", actions)

    def test_tui_row_action_mark_done_updates_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1 project:work\n")
            args = argparse.Namespace(paths=[path], config_data={})
            row = tui.selected_dashboard_row(args, 0)

            result = tui.perform_row_action("done", row, args)

            self.assertIn("Marked done: t1", result["message"])
            with open(path, "r", encoding="utf-8") as handle:
                self.assertIn("[x] T Write_Report", handle.read())

    def test_tui_selection_helpers_and_project_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "[ ] T Work_Task id:t1 project:work\n"
                    "[ ] T Home_Task id:t2 project:home\n"
                    "[/] S Focus from:2026-06-10T09:00 state:focus person:self\n"
                )
            args = argparse.Namespace(paths=[path], config_data={})

            self.assertEqual(1, tui.move_selection(args, 0, 1))
            self.assertEqual("tasks", tui.section_for_selected_index(args, 0))
            filtered = tui.render_dashboard(args, project_filter="home")

        self.assertIn("Home_Task", filtered)
        self.assertNotIn("Work_Task", filtered)

    def test_render_dashboard_safe_shows_errors(self):
        output = tui.render_dashboard_safe(argparse.Namespace(paths=["missing.life.txt"]))

        self.assertIn("Could not load life.txt data.", output)
        self.assertIn("ERROR:", output)

    def test_curses_draw_clips_to_small_screen(self):
        class FakeScreen:
            def __init__(self):
                self.calls = []

            def getmaxyx(self):
                return (4, 12)

            def addstr(self, row, column, text):
                if row >= 4 or column + len(text) >= 12:
                    raise RuntimeError("out of bounds")
                self.calls.append((row, column, text))

        screen = FakeScreen()
        tui._draw_curses_text(
            screen,
            "lifetxt TUI with a very long title\nTASKS\n  [ ] T Example",
            "q quit  r reload",
            scroll=1,
        )

        self.assertTrue(screen.calls)
        self.assertTrue(all(len(call[2]) <= 11 for call in screen.calls))

    def test_curses_draw_uses_color_attributes_when_available(self):
        class FakeScreen:
            def __init__(self):
                self.calls = []

            def getmaxyx(self):
                return (5, 40)

            def addstr(self, row, column, text, attr=0):
                self.calls.append((row, column, text, attr))

        screen = FakeScreen()
        tui._draw_curses_text(
            screen,
            "lifetxt TUI\n> TASKS (open)\n  [/] T Active_Task",
            "q quit",
            color_attrs={"title": 11, "focus": 22, "active": 33, "footer": 44},
        )

        attrs = [call[3] for call in screen.calls]
        self.assertIn(11, attrs)
        self.assertIn(22, attrs)
        self.assertIn(33, attrs)
        self.assertIn(44, attrs)

    def test_curses_mono_theme_keeps_selected_reverse_attr(self):
        class FakeCurses:
            A_BOLD = 1
            A_REVERSE = 2
            A_DIM = 4

            @staticmethod
            def has_colors():
                return True

        attrs = tui._init_curses_colors(FakeCurses, theme="mono")

        self.assertEqual(2, attrs["selected"])

    def test_clip_display_width_handles_wide_characters(self):
        self.assertEqual("あい", tui._clip_display_width("あいう", 4))
        self.assertEqual("ab", tui._clip_display_width("abc", 2))

    def test_section_navigation(self):
        self.assertEqual("agenda", tui.next_section("tasks"))
        self.assertEqual("status", tui.previous_section("tasks"))

    def test_vim_scroll_helpers_and_line_styles(self):
        class FakeScreen:
            def getmaxyx(self):
                return (4, 20)

        self.assertEqual(1, tui._page_scroll_amount(FakeScreen()))
        self.assertEqual(2, tui._max_scroll_for_screen(FakeScreen(), "a\nb\nc\nd\ne\n"))
        self.assertEqual("title", tui._style_for_line("lifetxt TUI"))
        self.assertEqual("focus", tui._style_for_line("> TASKS (open)"))
        self.assertEqual("selected", tui._style_for_line("* [ ] T Selected"))
        self.assertEqual("active", tui._style_for_line("  [/] T Active_Task"))
        self.assertEqual("error", tui._style_for_line("ERROR: broken"))

    def test_file_change_watcher_detects_polling_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T One id:t1\n")
            watcher = tui.FileChangeWatcher([path], use_watchdog=False).start()

            self.assertFalse(watcher.consume_changed())
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Two_Longer id:t1\n")

            self.assertTrue(watcher.consume_changed())
            self.assertFalse(watcher.consume_changed())


class WorkspaceStateTests(unittest.TestCase):
    """Coverage for the prompt-first workspace in lifetxt.tui_app."""

    SAMPLE = (
        "[ ] T Write_Report id:t1 project:work due:2099-12-31 priority:high\n"
        "[/] T Ship_Release id:t2 project:core\n"
        "[ ] T Buy_Milk id:t3 project:home\n"
    )

    def _state(self, text=None, **config):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        path = os.path.join(self._tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.SAMPLE if text is None else text)
        args = argparse.Namespace(paths=[path], config_data={"tui": config} if config else {})
        state = tui_app.WorkspaceState(args, glyphs=tui_app.UNICODE_GLYPHS)
        state.reload()
        return state, path

    def test_reload_collects_rows_and_counts(self):
        state, _path = self._state()

        self.assertEqual(3, len(state.rows))
        self.assertEqual(3, state.counts["tasks"])
        self.assertEqual("Write_Report", state.rows[0]["title"])

    def test_fuzzy_match_prefers_substring_over_scattered_subsequence(self):
        substring = tui_app.fuzzy_match("rep", "Write_Report")
        scattered = tui_app.fuzzy_match("wrp", "Write_Report")

        self.assertIsNotNone(substring)
        self.assertIsNotNone(scattered)
        self.assertGreater(substring[0], scattered[0])
        self.assertIsNone(tui_app.fuzzy_match("zzz", "Write_Report"))

    def test_typing_in_the_input_filters_rows_live(self):
        state, _path = self._state()

        state.input = "milk"
        state.reload()

        self.assertEqual(["Buy_Milk"], [row["title"] for row in state.rows])

    def test_enter_commits_a_plain_query_and_clears_the_input(self):
        state, _path = self._state()
        state.input = "milk"
        state.cursor = 4

        tui_app.handle_key(state, "enter")
        state.reload()

        self.assertEqual("milk", state.query)
        self.assertEqual("", state.input)
        self.assertEqual(["Buy_Milk"], [row["title"] for row in state.rows])

    def test_slash_opens_the_palette_and_tab_completes_a_command(self):
        state, _path = self._state()

        for char in "/vie":
            tui_app.handle_key(state, char)

        self.assertTrue(state.palette_open)
        suggestions = tui_app.command_suggestions(state.input)
        self.assertEqual("view", suggestions[0][0].name)

        tui_app.handle_key(state, "tab")
        self.assertEqual("/view ", state.input)

    def test_running_a_command_switches_the_view(self):
        state, _path = self._state()

        level, message = tui_app.run_command(state, "/view tasks")

        self.assertEqual("info", level)
        self.assertIn("tasks", message)
        self.assertEqual("tasks", state.view)

    def test_unknown_command_suggests_the_closest_name(self):
        state, _path = self._state()

        with self.assertRaises(ValueError) as caught:
            tui_app.run_command(state, "/vew")

        self.assertIn("/view", str(caught.exception))

    def test_sort_by_priority_puts_high_priority_first(self):
        state, _path = self._state()

        tui_app.run_command(state, "/sort priority")
        state.reload()

        self.assertEqual("Write_Report", state.rows[0]["title"])

    def test_mark_all_then_done_updates_every_marked_row(self):
        state, path = self._state()

        tui_app.run_command(state, "/mark all")
        self.assertEqual(3, len(state.marked))
        level, message = tui_app.run_command(state, "/done")

        self.assertEqual("success", level)
        self.assertIn("t1", message)
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertEqual(3, content.count("[x] T"))
        self.assertEqual(set(), state.marked)

    def test_bulk_done_is_rejected_whole_when_one_row_cannot_be_completed(self):
        state, path = self._state(
            "[ ] T A id:t1 project:work\n[ ] T NoIdTask project:work\n[ ] T C id:t3 project:work\n"
        )

        tui_app.run_command(state, "/mark all")
        with self.assertRaises(ValueError) as caught:
            tui_app.run_command(state, "/done")

        self.assertIn("NoIdTask", str(caught.exception))
        with open(path, "r", encoding="utf-8") as handle:
            self.assertNotIn("[x]", handle.read())

    def test_one_undo_reverts_a_whole_bulk_done(self):
        state, path = self._state()

        tui_app.run_command(state, "/mark all")
        tui_app.run_command(state, "/done")
        tui_app.run_command(state, "/undo")

        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(self.SAMPLE, handle.read())

    def test_refresh_filters_without_re_parsing_the_files(self):
        state, _path = self._state()
        before = state.load_count

        for char in "milk":
            tui_app.handle_key(state, char)
            state.refresh()

        self.assertEqual(before, state.load_count)
        self.assertEqual(["Buy_Milk"], [row["title"] for row in state.rows])

    def test_limit_applies_inside_a_single_section_view(self):
        rows = "".join("[ ] T Task%02d id:t%02d\n" % (index, index) for index in range(30))
        state, _path = self._state(rows, limit=5)

        tui_app.run_command(state, "/view tasks")
        state.refresh()

        self.assertEqual(5, len(state.rows))

    def test_undo_restores_the_file_after_a_done_write(self):
        state, path = self._state()

        tui_app.run_command(state, "/done")
        tui_app.run_command(state, "/undo")

        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(self.SAMPLE, handle.read())

    def test_add_appends_a_new_task_through_the_safe_write_path(self):
        state, path = self._state()

        level, message = tui_app.run_command(state, "/add Call the dentist")

        self.assertEqual("success", level)
        self.assertIn("Call", message)
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn('[ ] T "Call the dentist"', content)
        items, diagnostics = parse_text(content)
        self.assertEqual([], [d for d in diagnostics if d.severity == "error"])
        self.assertEqual(4, len(items))

    def test_project_filter_and_clear_round_trip(self):
        state, _path = self._state()

        tui_app.run_command(state, "/project home")
        state.reload()
        self.assertEqual(["Buy_Milk"], [row["title"] for row in state.rows])

        tui_app.run_command(state, "/clear")
        state.reload()
        self.assertEqual(3, len(state.rows))

    def test_command_history_recall_with_ctrl_p(self):
        state, _path = self._state()
        state.input = "milk"
        tui_app.handle_key(state, "enter")

        tui_app.handle_key(state, "ctrl-p")

        self.assertEqual("milk", state.input)

    def test_vim_keymap_starts_in_nav_mode_and_moves_with_jk(self):
        state, _path = self._state(keymap="vim")

        self.assertEqual("nav", state.mode)
        tui_app.handle_key(state, "j")
        self.assertEqual(1, state.selected)
        tui_app.handle_key(state, "k")
        self.assertEqual(0, state.selected)

        tui_app.handle_key(state, "/")
        self.assertEqual("input", state.mode)

    def test_escape_clears_the_input_then_the_filters(self):
        state, _path = self._state()
        state.input = "milk"
        tui_app.handle_key(state, "enter")

        tui_app.handle_key(state, "escape")

        self.assertEqual("", state.query)

    def test_line_editing_keys_operate_on_the_input_buffer(self):
        state, _path = self._state()
        for char in "hello":
            tui_app.handle_key(state, char)

        tui_app.handle_key(state, "ctrl-a")
        tui_app.handle_key(state, "delete")

        self.assertEqual("ello", state.input)
        self.assertEqual(0, state.cursor)


class WorkspaceKeymapRegressionTests(unittest.TestCase):
    """Regressions for the two reported TUI bugs."""

    def _state(self, keymap):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T A id:t1\n[ ] T B id:t2\n")
        args = argparse.Namespace(paths=[path], config_data={"tui": {"keymap": keymap}})
        state = tui_app.WorkspaceState(args, glyphs=tui_app.ASCII_GLYPHS)
        state.reload()
        return state

    def test_vim_mode_returns_to_nav_after_closing_help_opened_by_command(self):
        state = self._state("vim")

        tui_app.handle_key(state, ":")
        for char in "help":
            tui_app.handle_key(state, char)
        tui_app.handle_key(state, "enter")
        self.assertTrue(state.show_help)

        tui_app.handle_key(state, "enter")

        self.assertFalse(state.show_help)
        self.assertEqual("nav", state.mode)
        # j must navigate again instead of being typed into the input bar.
        tui_app.handle_key(state, "j")
        self.assertEqual("", state.input)
        self.assertEqual(1, state.selected)

    def test_vim_mode_returns_to_nav_after_a_search(self):
        state = self._state("vim")

        tui_app.handle_key(state, "/")
        self.assertEqual("input", state.mode)
        for char in "a":
            tui_app.handle_key(state, char)
        tui_app.handle_key(state, "enter")

        self.assertEqual("nav", state.mode)
        self.assertEqual("a", state.query)

    def test_vim_mode_returns_to_nav_after_escaping_an_empty_input(self):
        state = self._state("vim")

        tui_app.handle_key(state, "/")
        tui_app.handle_key(state, "escape")

        self.assertEqual("nav", state.mode)

    def test_prompt_keymap_keeps_the_input_bar_focused(self):
        state = self._state("prompt")

        tui_app.handle_key(state, "/")
        for char in "help":
            tui_app.handle_key(state, char)
        tui_app.handle_key(state, "enter")
        tui_app.handle_key(state, "enter")

        self.assertEqual("input", state.mode)

    def test_help_overlay_scrolls_and_resets_on_close(self):
        state = self._state("prompt")
        state.show_help = True

        tui_app.handle_key(state, "down")
        tui_app.handle_key(state, "down")
        self.assertEqual(2, state.help_scroll)

        tui_app.handle_key(state, "escape")
        self.assertFalse(state.show_help)
        self.assertEqual(0, state.help_scroll)


class WorkspaceInterruptTests(unittest.TestCase):
    """Ctrl-C must leave the TUI quietly rather than raising KeyboardInterrupt.

    curses.wrapper uses cbreak(), which leaves ISIG enabled, so a real terminal
    delivers SIGINT instead of key code 3.
    """

    def _curses_raising_on_getch(self):
        module = types.ModuleType("curses")
        for index, name in enumerate(("KEY_UP", "KEY_DOWN", "KEY_RESIZE", "KEY_ENTER")):
            setattr(module, name, 300 + index)
        for index, name in enumerate(("A_BOLD", "A_DIM", "A_REVERSE", "A_UNDERLINE")):
            setattr(module, name, 1 << index)
        for index, name in enumerate(("COLOR_BLACK", "COLOR_BLUE", "COLOR_CYAN", "COLOR_WHITE")):
            setattr(module, name, index)
        module.has_colors = lambda: False
        module.curs_set = lambda number: None

        class Screen:
            def getmaxyx(self):
                return (24, 80)

            def timeout(self, milliseconds):
                pass

            def erase(self):
                pass

            def refresh(self):
                pass

            def move(self, row, column):
                pass

            def addstr(self, row, column, text, attr=0):
                pass

            def getch(self):
                raise KeyboardInterrupt()

        module.wrapper = lambda main: main(Screen())
        return module

    def test_workspace_exits_cleanly_on_sigint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T A id:t1\n")
            args = argparse.Namespace(paths=[path], config_data={"tui": {"session": "off"}})
            with patch.dict(sys.modules, {"curses": self._curses_raising_on_getch()}):
                result = tui_app.run_workspace(args)

        self.assertEqual(0, result)

    def test_cmd_tui_swallows_sigint_from_the_interactive_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T A id:t1\n")
            args = argparse.Namespace(paths=[path], config_data={}, plain=False)

            def boom(_args):
                raise KeyboardInterrupt()

            with patch.object(tui, "_stdout_is_tty", lambda: True), \
                    patch.dict(sys.modules, {"curses": types.ModuleType("curses")}), \
                    patch("lifetxt.tui_app.run_workspace", boom):
                result = tui.cmd_tui(args)

        self.assertEqual(0, result)


class WorkspaceCommandTests(unittest.TestCase):
    """Coverage for the row-editing, filtering, and export commands."""

    SAMPLE = (
        "[ ] T Write_Report id:t1 project:work due:2099-12-31 priority:high context:office tag:urgent\n"
        "[/] T Ship_Release id:t2 project:core\n"
        "[ ] T Buy_Milk id:t3 project:home context:errand\n"
        "[?] T Someday_Idea id:t4 project:home\n"
    )

    def _state(self, text=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(self.SAMPLE if text is None else text)
        args = argparse.Namespace(
            paths=[path],
            config_data={"tui": {"session": "off"}, "timer": {"state_file": os.path.join(tmp.name, "timer.json")}},
        )
        state = tui_app.WorkspaceState(args, glyphs=tui_app.ASCII_GLYPHS)
        state.reload()
        return state, path, tmp.name

    def _line_for(self, path, item_id):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if "id:%s" % item_id in line:
                    return line.rstrip("\n")
        raise AssertionError("no line with id:%s" % item_id)

    def test_context_filter_narrows_and_clears(self):
        state, _path, _tmp = self._state()

        tui_app.run_command(state, "/context office")
        state.refresh()
        self.assertEqual(["Write_Report"], [row["title"] for row in state.rows])

        tui_app.run_command(state, "/context")
        state.refresh()
        self.assertEqual(4, len(state.rows))

    def test_tag_filter_narrows_and_ignores_a_leading_hash(self):
        state, _path, _tmp = self._state()

        tui_app.run_command(state, "/tag #urgent")
        state.refresh()

        self.assertEqual(["Write_Report"], [row["title"] for row in state.rows])

    def test_next_view_excludes_someday_and_blocked_rows(self):
        state, _path, _tmp = self._state(
            self.SAMPLE + "[ ] T Blocked_Task id:t5 depends_on:t1\n[ ] T Maybe_Task id:t6 tag:someday\n"
        )

        tui_app.run_command(state, "/next")
        state.refresh()
        titles = [row["title"] for row in state.rows]

        self.assertIn("Write_Report", titles)
        self.assertNotIn("Someday_Idea", titles)
        self.assertNotIn("Blocked_Task", titles)
        self.assertNotIn("Maybe_Task", titles)

    def test_goto_moves_the_selection_to_a_record_id(self):
        state, _path, _tmp = self._state()

        tui_app.run_command(state, "/goto t3")

        self.assertEqual("Buy_Milk", state.selected_row()["title"])
        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/goto nope")

    def test_set_writes_a_detail_and_an_empty_value_removes_it(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t2")

        tui_app.run_command(state, "/set owner dana")
        self.assertIn("owner:dana", self._line_for(path, "t2"))

        tui_app.run_command(state, "/goto t2")
        tui_app.run_command(state, "/set owner")
        self.assertNotIn("owner:", self._line_for(path, "t2"))

    def test_due_accepts_relative_tokens(self):
        import datetime as _datetime

        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")

        tui_app.run_command(state, "/due +3d")

        expected = (_datetime.date.today() + _datetime.timedelta(days=3)).isoformat()
        self.assertIn("due:%s" % expected, self._line_for(path, "t3"))

    def test_agenda_rows_carry_their_source_and_stay_editable(self):
        # A task whose due date falls inside the agenda window appears in both
        # the tasks and agenda sections. The agenda copy used to lose its source
        # file, which made every editing command fail on it.
        soon = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        state, path, _tmp = self._state("[ ] T Soon_Task id:t1 project:work due:%s\n" % soon)

        agenda_rows = [row for row in state.rows if row["section"] == "agenda"]
        self.assertTrue(agenda_rows, "expected the due task to appear in the agenda section")
        for row in agenda_rows:
            self.assertTrue(row.get("source"), "agenda row is missing its source file")

        state.selected = state.rows.index(agenda_rows[0])
        level, _message = tui_app.run_command(state, "/done")

        self.assertEqual("success", level)
        with open(path, "r", encoding="utf-8") as handle:
            self.assertIn("[x] T Soon_Task", handle.read())

    def test_due_rejects_a_value_that_is_not_a_date(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")

        for bad in ("notadate", "2026-13-99"):
            with self.assertRaises(ValueError) as caught:
                tui_app.run_command(state, "/due %s" % bad)
            self.assertIn("is not a date", str(caught.exception))

        self.assertNotIn("due:", self._line_for(path, "t3"))

    def test_limit_truncation_is_reported_rather_than_silent(self):
        rows = "".join("[ ] T Task%02d id:t%02d\n" % (index, index) for index in range(30))
        state, _path, _tmp = self._state(rows)
        state.options["limit"] = 10
        state.refresh()

        self.assertEqual(10, len(state.rows))
        self.assertEqual(20, state.hidden.get("tasks"))

        # Visible on the section header, which cannot scroll out of view...
        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 22))
        self.assertIn("TASKS 10/30", text)
        # ...and as a trailing row when the list is tall enough to reach it.
        self.assertIn("more hidden by limit", tui_app.frame_to_text(tui_app.build_frame(state, 92, 40)))

    def test_sorted_views_still_honour_the_limit(self):
        rows = "".join("[ ] T Task%02d id:t%02d\n" % (index, index) for index in range(30))
        state, _path, _tmp = self._state(rows)
        state.options["limit"] = 10

        tui_app.run_command(state, "/next")
        state.refresh()

        self.assertEqual(10, len(state.rows))
        self.assertEqual(20, state.hidden.get("tasks"))

    def test_status_uses_aliases_and_rejects_unknown_values(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t1")

        tui_app.run_command(state, "/status active")
        self.assertTrue(self._line_for(path, "t1").startswith("[/]"))

        tui_app.run_command(state, "/goto t1")
        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/status nonsense")

    def test_assign_sets_and_clears_the_assignee(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")

        tui_app.run_command(state, "/assign carol")
        self.assertIn("assignee:carol", self._line_for(path, "t3"))

    def test_bulk_set_applies_to_every_marked_row_with_one_undo(self):
        state, path, _tmp = self._state()

        tui_app.run_command(state, "/mark all")
        tui_app.run_command(state, "/set owner dana")

        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(4, handle.read().count("owner:dana"))

        tui_app.run_command(state, "/undo")
        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(self.SAMPLE, handle.read())

    def test_delete_requires_confirmation_then_removes_the_row(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")

        with self.assertRaises(ValueError) as caught:
            tui_app.run_command(state, "/delete")
        self.assertIn("/delete yes", str(caught.exception))
        with open(path, "r", encoding="utf-8") as handle:
            self.assertIn("Buy_Milk", handle.read())

        tui_app.run_command(state, "/goto t3")
        tui_app.run_command(state, "/delete yes")
        with open(path, "r", encoding="utf-8") as handle:
            self.assertNotIn("Buy_Milk", handle.read())

        tui_app.run_command(state, "/undo")
        with open(path, "r", encoding="utf-8") as handle:
            self.assertIn("Buy_Milk", handle.read())

    def test_editing_a_row_without_an_id_is_rejected_before_any_write(self):
        state, path, _tmp = self._state("[ ] T HasId id:t1\n[ ] T NoId project:x\n")

        tui_app.run_command(state, "/mark all")
        with self.assertRaises(ValueError) as caught:
            tui_app.run_command(state, "/set owner dana")

        self.assertIn("NoId", str(caught.exception))
        with open(path, "r", encoding="utf-8") as handle:
            self.assertNotIn("owner:", handle.read())

    def test_timer_start_status_and_stop_write_elapsed(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")

        self.assertIn("No running timer", tui_app.run_command(state, "/timer status")[1])
        tui_app.run_command(state, "/timer start")
        self.assertIn("t3", tui_app.run_command(state, "/timer status")[1])
        level, message = tui_app.run_command(state, "/timer stop")

        self.assertEqual("success", level)
        self.assertIn("elapsed:", self._line_for(path, "t3"))

    def test_timer_start_refuses_a_second_concurrent_timer(self):
        state, _path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")
        tui_app.run_command(state, "/timer start")

        tui_app.run_command(state, "/goto t1")
        with self.assertRaises(ValueError) as caught:
            tui_app.run_command(state, "/timer start")

        self.assertIn("already running", str(caught.exception))

    def test_timer_cancel_discards_the_session_without_writing_elapsed(self):
        state, path, _tmp = self._state()
        tui_app.run_command(state, "/goto t3")
        tui_app.run_command(state, "/timer start")

        tui_app.run_command(state, "/timer cancel")

        self.assertNotIn("elapsed:", self._line_for(path, "t3"))
        self.assertIn("No running timer", tui_app.run_command(state, "/timer status")[1])

    def test_export_writes_markdown_csv_and_json(self):
        state, _path, tmp = self._state()

        for fmt in tui_app.EXPORT_FORMATS:
            target = os.path.join(tmp, "out.%s" % fmt)
            level, _message = tui_app.run_command(state, "/export %s %s" % (fmt, target))
            self.assertEqual("success", level)
            with open(target, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Write_Report", content)

        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/export xml")

    def test_export_json_round_trips_and_csv_has_a_header(self):
        import json as _json

        state, _path, _tmp = self._state()

        payload = _json.loads(tui_app.render_export(state.rows, "json"))
        self.assertEqual(4, len(payload))
        self.assertEqual("Write_Report", payload[0]["title"])

        csv_text = tui_app.render_export(state.rows, "csv")
        self.assertTrue(csv_text.startswith("section,status,type,title,id,project,due,priority"))

    def test_help_search_ranks_matching_commands(self):
        state, _path, _tmp = self._state()

        level, message = tui_app.run_command(state, "/help timer")

        self.assertEqual("info", level)
        self.assertTrue(state.show_help)
        self.assertEqual("timer", state.help_query)
        self.assertIn("/timer", tui_app.help_entries("timer")[0][0])

        with self.assertRaises(ValueError):
            tui_app.run_command(state, "/help zzzzqqq")

    def test_per_field_scoring_ranks_a_title_hit_above_a_detail_hit(self):
        title_hit = {"title": "work", "details": {}}
        detail_hit = {"title": "Something", "details": {"note": ["work"]}}

        self.assertGreater(
            tui_app.score_row("work", title_hit)[0],
            tui_app.score_row("work", detail_hit)[0],
        )

    def test_session_round_trips_view_sort_and_filters(self):
        state, _path, _tmp = self._state()
        state.view = "tasks"
        state.sort = "priority"
        state.project = "home"
        state.context = "errand"
        state.history = ["/done"]

        payload = tui_app.session_payload(state)
        restored = tui_app.WorkspaceState(state.args, glyphs=tui_app.ASCII_GLYPHS)
        tui_app.apply_session(restored, payload)

        self.assertEqual("tasks", restored.view)
        self.assertEqual("priority", restored.sort)
        self.assertEqual("home", restored.project)
        self.assertEqual("errand", restored.context)
        self.assertEqual(["/done"], restored.history)

    def test_session_ignores_values_that_are_no_longer_valid(self):
        state, _path, _tmp = self._state()

        tui_app.apply_session(state, {"view": "bogus", "sort": "bogus", "project": 42, "history": "nope"})

        self.assertEqual("all", state.view)
        self.assertEqual("natural", state.sort)
        self.assertIsNone(state.project)

    def test_session_save_and_load_use_the_configured_path(self):
        state, _path, tmp = self._state()
        state.args.config_data["tui"] = {"session_file": os.path.join(tmp, "session.json")}
        state.view = "tasks"
        state.sort = "title"

        self.assertTrue(tui_app.save_session(state))
        restored = tui_app.WorkspaceState(state.args, glyphs=tui_app.ASCII_GLYPHS)
        self.assertTrue(tui_app.load_session(restored))

        self.assertEqual("tasks", restored.view)
        self.assertEqual("title", restored.sort)

    def test_session_can_be_disabled_in_config(self):
        state, _path, _tmp = self._state()

        self.assertFalse(tui_app.save_session(state))
        self.assertFalse(tui_app.load_session(state))


class WorkspaceFrameTests(unittest.TestCase):
    def _state(self, text="[ ] T Write_Report id:t1 project:work due:2099-12-31 priority:high\n"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        args = argparse.Namespace(paths=[path], config_data={})
        state = tui_app.WorkspaceState(args, glyphs=tui_app.UNICODE_GLYPHS)
        state.reload()
        return state

    def test_frame_has_exact_height_and_never_exceeds_width(self):
        state = self._state()

        frame = tui_app.build_frame(state, 92, 30)

        self.assertEqual(30, len(frame))
        for line in frame:
            self.assertLessEqual(tui_app.display_width(tui_app.spans_to_text(line)), 92)

    def test_frame_shows_the_header_prompt_and_selected_row(self):
        state = self._state()

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        self.assertIn("lifetxt", text)
        self.assertIn("workspace", text)
        self.assertIn("Write_Report", text)
        self.assertIn("TASKS", text)
        self.assertIn("type to filter", text)

    def test_wide_characters_keep_columns_aligned(self):
        state = self._state("[ ] T 日本語のタスク id:t1 project:home\n[ ] T Ascii_Task id:t2 project:home\n")

        frame = tui_app.build_frame(state, 92, 30)
        rows = [
            line
            for line in frame
            if any(style.startswith("status_") for _text, style in line)
        ]

        self.assertEqual(2, len(rows))
        widths = set(tui_app.display_width(tui_app.spans_to_text(line)) for line in rows)
        self.assertEqual(1, len(widths))

    def test_narrow_terminal_drops_meta_columns_instead_of_wrapping(self):
        self.assertEqual((), tui_app.meta_columns_for_width(40))
        self.assertEqual(1, len(tui_app.meta_columns_for_width(60)))
        self.assertEqual(3, len(tui_app.meta_columns_for_width(120)))

        state = self._state()
        frame = tui_app.build_frame(state, 44, 24)
        for line in frame:
            self.assertLessEqual(tui_app.display_width(tui_app.spans_to_text(line)), 44)

    def test_context_label_drops_whole_parts_instead_of_clipping_values(self):
        state = self._state()
        state.sort = "priority"
        state.query = "task"

        wide = tui_app._context_label(state, 80)
        narrow = tui_app._context_label(state, 20)

        self.assertIn("life.txt", wide)
        self.assertIn("sort:priority", wide)
        self.assertIn("search:task", wide)
        # The least important parts are shed first, and no value is half-written.
        self.assertEqual("search:task", narrow)
        self.assertEqual("", tui_app._context_label(state, 4))

    def test_palette_window_scrolls_to_keep_the_active_entry_visible(self):
        state = self._state()
        state.input = "/"
        for _ in range(10):
            tui_app.handle_key(state, "down")

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))
        active = tui_app.command_suggestions(state.input)[state.palette_index][0]

        self.assertGreater(state.palette_index, 5)
        self.assertIn("/" + active.name, text)

    def test_palette_renders_matching_commands_with_summaries(self):
        state = self._state()
        state.input = "/do"

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        self.assertIn("/done", text)
        self.assertIn("Mark the marked or selected task-like rows done", text)

    def test_two_pane_layout_appears_only_on_wide_terminals(self):
        state = self._state()

        wide = tui_app.frame_to_text(tui_app.build_frame(state, 130, 24))
        narrow = tui_app.frame_to_text(tui_app.build_frame(state, 90, 24))

        # In two-pane mode the selection panel sits beside the list, so its
        # border shares a line with a row rather than owning the line.
        wide_rows = [
            line
            for line in tui_app.build_frame(state, 130, 24)
            if any(style.startswith("status_") for _text, style in line)
            and "selection" not in tui_app.spans_to_text(line)
        ]
        self.assertTrue(wide_rows)
        self.assertIn("selection", wide)
        self.assertIn("selection", narrow)
        border = state.glyphs["v"]
        beside = [
            line
            for line in tui_app.build_frame(state, 130, 24)
            if any(style.startswith("status_") for _text, style in line)
            and tui_app.spans_to_text(line).rstrip().endswith(border)
        ]
        self.assertTrue(beside, "expected a row line to end with the side panel border")

    def test_two_pane_lines_never_exceed_the_terminal_width(self):
        state = self._state()

        for width in (118, 130, 200):
            for line in tui_app.build_frame(state, width, 24):
                self.assertLessEqual(tui_app.display_width(tui_app.spans_to_text(line)), width)

    def test_stats_panel_breaks_visible_rows_down(self):
        state = self._state("[ ] T A id:t1 project:work\n[x] T B id:t2 project:work\n[ ] T C id:t3 project:home\n")
        state.show_stats = True

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        self.assertIn("STATS", text)
        self.assertIn("by status", text)
        self.assertIn("by project", text)
        self.assertIn("work", text)

    def test_help_search_shows_only_matching_commands(self):
        state = self._state()
        state.show_help = True
        state.help_query = "timer"

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 40))

        self.assertIn("/timer", text)
        self.assertIn("matching", text)
        self.assertNotIn("/theme", text)

    def test_help_overlay_scrolls_when_it_exceeds_the_screen(self):
        state = self._state()
        state.show_help = True

        first = tui_app.frame_to_text(tui_app.build_frame(state, 92, 20))
        state.help_scroll = 12
        second = tui_app.frame_to_text(tui_app.build_frame(state, 92, 20))

        self.assertIn("more line(s) below", first)
        self.assertNotEqual(first, second)

    def test_help_overlay_lists_every_command(self):
        state = self._state()
        state.show_help = True

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 60))

        self.assertIn("COMMANDS", text)
        self.assertIn("KEYS", text)
        for command in tui_app.COMMANDS:
            self.assertIn("/" + command.name, text)

    def test_empty_state_explains_how_to_recover(self):
        state = self._state()
        state.query = "nothing-matches-this"
        state.reload()

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        self.assertIn("No row matches", text)
        self.assertIn("/clear", text)

    def test_broken_file_renders_an_error_panel_instead_of_crashing(self):
        state = self._state()
        state.args.paths = ["missing.life.txt"]
        state.reload()

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        self.assertIn("Could not load life.txt data.", text)
        self.assertIn("/reload", text)

    def test_ascii_glyphs_keep_the_frame_pure_ascii(self):
        state = self._state()
        state.glyphs = tui_app.ASCII_GLYPHS

        text = tui_app.frame_to_text(tui_app.build_frame(state, 92, 30))

        text.encode("ascii")

    def test_toast_message_is_rendered_and_expires(self):
        state = self._state()
        state.notify("Marked done: t1", "success")

        self.assertIn("Marked done: t1", tui_app.frame_to_text(tui_app.build_frame(state, 92, 30)))

        state.toast.created -= tui_app.TOAST_SECONDS + 1
        self.assertTrue(state.toast.expired())

    def test_highlight_spans_split_matched_characters(self):
        spans = tui_app.highlight_spans("Report", [0, 1], "row")

        self.assertEqual([("Re", "match"), ("port", "row")], spans)

    def test_draw_frame_clips_to_a_small_screen(self):
        class FakeScreen:
            def __init__(self):
                self.calls = []

            def getmaxyx(self):
                return (3, 10)

            def addstr(self, row, column, text, attr=0):
                if row >= 3 or column + len(text) >= 10:
                    raise RuntimeError("out of bounds")
                self.calls.append((row, column, text, attr))

        screen = FakeScreen()
        state = self._state()
        tui_app.draw_frame(screen, tui_app.build_frame(state, 92, 30), {"brand": 7})

        self.assertTrue(all(call[0] < 3 for call in screen.calls))

    def test_normalize_key_maps_control_and_special_codes(self):
        class FakeCurses:
            KEY_UP = 259
            KEY_DOWN = 258

        self.assertEqual("up", tui_app.normalize_key(FakeCurses, 259))
        self.assertEqual("enter", tui_app.normalize_key(FakeCurses, 10))
        self.assertEqual("tab", tui_app.normalize_key(FakeCurses, 9))
        self.assertEqual("escape", tui_app.normalize_key(FakeCurses, 27))
        self.assertEqual("ctrl-t", tui_app.normalize_key(FakeCurses, 20))
        self.assertEqual("a", tui_app.normalize_key(FakeCurses, 97))


class WorkspaceRunnerTests(unittest.TestCase):
    """Drive run_workspace with a stub curses module so the interactive loop is
    covered on machines without a real curses build (notably Windows)."""

    def _fake_curses(self, screen):
        module = types.ModuleType("curses")
        specials = (
            "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "KEY_HOME", "KEY_END",
            "KEY_NPAGE", "KEY_PPAGE", "KEY_BACKSPACE", "KEY_ENTER", "KEY_RESIZE", "KEY_DC",
        )
        for index, name in enumerate(specials):
            setattr(module, name, 300 + index)
        for index, name in enumerate(("A_BOLD", "A_DIM", "A_REVERSE", "A_UNDERLINE")):
            setattr(module, name, 1 << index)
        colors = (
            "COLOR_BLACK", "COLOR_RED", "COLOR_GREEN", "COLOR_YELLOW",
            "COLOR_BLUE", "COLOR_MAGENTA", "COLOR_CYAN", "COLOR_WHITE",
        )
        for index, name in enumerate(colors):
            setattr(module, name, index)
        module.has_colors = lambda: True
        module.start_color = lambda: None
        module.use_default_colors = lambda: None
        module.init_pair = lambda *args: None
        module.color_pair = lambda number: number << 8
        module.curs_set = lambda number: None
        module.wrapper = lambda main: main(screen)
        return module

    class _Screen:
        def __init__(self, keys):
            self.keys = list(keys)
            self.drawn = []
            self.cursor = None

        def getmaxyx(self):
            return (30, 92)

        def timeout(self, milliseconds):
            pass

        def erase(self):
            pass

        def refresh(self):
            pass

        def move(self, row, column):
            self.cursor = (row, column)

        def addstr(self, row, column, text, attr=0):
            self.drawn.append((row, column, text, attr))

        def getch(self):
            return self.keys.pop(0) if self.keys else 3

    def test_session_filters_then_marks_done_and_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Write_Report id:t1 project:work\n[ ] T Buy_Milk id:t3 project:home\n")

            keys = [ord(char) for char in "milk"] + [10] + [ord(char) for char in "/done"] + [10] + [3]
            screen = self._Screen(keys)
            args = argparse.Namespace(paths=[path], config_data={})
            with patch.dict(sys.modules, {"curses": self._fake_curses(screen)}):
                result = tui_app.run_workspace(args)

            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

        self.assertEqual(0, result)
        self.assertTrue(screen.drawn)
        self.assertIsNotNone(screen.cursor)
        self.assertIn("[x] T Buy_Milk", content)
        self.assertIn("[ ] T Write_Report", content)

    def test_ctrl_c_exits_immediately_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            original = "[ ] T Write_Report id:t1\n"
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(original)

            screen = self._Screen([3])
            args = argparse.Namespace(paths=[path], config_data={})
            with patch.dict(sys.modules, {"curses": self._fake_curses(screen)}):
                result = tui_app.run_workspace(args)

            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(original, handle.read())

        self.assertEqual(0, result)


class TuiFallbackTests(unittest.TestCase):
    """Stabilization coverage for the P0 item: confirm graceful fallback when
    optional dependencies (textual, curses) are unavailable, on whatever
    platform the tests run on."""

    def _life_path(self, tmp):
        path = os.path.join(tmp, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Sample project:work\n")
        return path

    def _with_module_forced_missing(self, name, body):
        had_module = name in sys.modules
        original = sys.modules.get(name)
        sys.modules[name] = None
        try:
            return body()
        finally:
            if had_module:
                sys.modules[name] = original
            else:
                sys.modules.pop(name, None)

    def test_run_textual_falls_back_when_textual_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(paths=[self._life_path(tmp)])
            output = io.StringIO()

            def run():
                with redirect_stdout(output):
                    return tui.run_textual(args)

            result = self._with_module_forced_missing("textual", run)

        self.assertEqual(0, result)
        self.assertIn("lifetxt TUI", output.getvalue())
        self.assertIn("TASKS", output.getvalue())

    def test_run_curses_or_plain_falls_back_to_plain_text_when_curses_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(paths=[self._life_path(tmp)])
            output = io.StringIO()

            def run():
                with redirect_stdout(output):
                    return tui.run_curses_or_plain(args)

            result = self._with_module_forced_missing("curses", run)

        self.assertEqual(0, result)
        self.assertIn("lifetxt TUI", output.getvalue())
        self.assertIn("Install textual for a richer TUI", output.getvalue())

    def test_cmd_tui_never_crashes_regardless_of_optional_deps(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(paths=[self._life_path(tmp)])
            output = io.StringIO()
            with redirect_stdout(output):
                result = tui.cmd_tui(args)
        self.assertEqual(0, result)
        self.assertIn("lifetxt TUI", output.getvalue())


class FzfPreviewQuotingTests(unittest.TestCase):
    """Stabilization coverage for the P0 item: confirm fzf preview-command
    quoting is correct for both POSIX shells and native Windows cmd.exe."""

    def test_posix_shell_uses_shlex_quote_form(self):
        with patch.object(fzf_helper.os, "name", "posix"):
            command = fzf_helper._preview_command()
        self.assertIn("fzf-preview {1}", command)
        self.assertFalse(command.startswith('"'))

    def test_native_windows_without_shell_uses_double_quote_form(self):
        with patch.object(fzf_helper.os, "name", "nt"), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SHELL", None)
            command = fzf_helper._preview_command()
        self.assertTrue(command.startswith('"'))
        self.assertIn("fzf-preview {1}", command)

    def test_windows_with_posix_shell_uses_shlex_quote_form(self):
        # git-bash / WSL / MSYS builds of fzf set $SHELL and run the preview
        # command through a POSIX shell even on Windows.
        with patch.object(fzf_helper.os, "name", "nt"), patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            command = fzf_helper._preview_command()
        self.assertFalse(command.startswith('"'))
        self.assertIn("fzf-preview {1}", command)


class FzfNotInstalledTests(unittest.TestCase):
    """Stabilization coverage for the P0 item: confirm a clear, actionable
    error when neither fzf nor peco is installed."""

    def test_resolve_tool_raises_clear_error_when_missing(self):
        with patch("shutil.which", return_value=None):
            with self.assertRaises(ValueError) as ctx:
                fzf_helper.resolve_tool()
        self.assertIn("fzf or peco was not found in PATH", str(ctx.exception))

    def test_cmd_fzf_cli_reports_clear_error_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Sample\n")
            env = os.environ.copy()
            env["PATH"] = tmp  # a directory guaranteed not to contain fzf/peco
            process = subprocess.Popen(
                [sys.executable, "-m", "lifetxt", "fzf", path],
                cwd=ROOT_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = process.communicate()
        self.assertEqual(1, process.returncode)
        self.assertIn("fzf or peco was not found in PATH", stderr.decode("utf-8"))


class PlotPngFallbackTests(unittest.TestCase):
    """Stabilization coverage for the P0 item: confirm a clear error when
    --format png is requested without matplotlib installed, and a real PNG
    when it is."""

    def test_missing_matplotlib_gives_clear_error(self):
        had_module = "matplotlib" in sys.modules
        original = sys.modules.get("matplotlib")
        sys.modules["matplotlib"] = None
        try:
            with self.assertRaises(ValueError) as ctx:
                cli._plot_data_to_png({"Tasks": {"done": 3}}, os.devnull)
        finally:
            if had_module:
                sys.modules["matplotlib"] = original
            else:
                sys.modules.pop("matplotlib", None)
        self.assertIn("--format png requires matplotlib", str(ctx.exception))
        self.assertIn("--format svg", str(ctx.exception))

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("matplotlib") is not None,
        "matplotlib is not installed in this environment",
    )
    def test_png_output_written_when_matplotlib_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "chart.png")
            cli._plot_data_to_png({"Tasks": {"done": 3, "open": 1}}, output_path)
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "rb") as handle:
                self.assertEqual(b"\x89PNG", handle.read(4))


class TimerMultiCycleTests(unittest.TestCase):
    """Extra stabilization coverage: several pause/resume cycles in a single
    session must accumulate elapsed time correctly, not just one cycle."""

    def test_three_pause_resume_cycles_accumulate_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "life.txt")
            state_file = os.path.join(tmp, "timer.json")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("[ ] T Deep_Work id:t1\n")
            config_data = {"timer": {"state_file": state_file}}
            start_args = argparse.Namespace(path=path, item_id="t1", note=None, config_data=config_data)
            command_args = argparse.Namespace(config_data=config_data)
            stop_args = argparse.Namespace(path=None, item_id=None, config_data=config_data)

            # Three 10-minute work intervals separated by pauses: expect 30m total.
            ticks = [
                (0, "start"), (10, "pause"), (20, "resume"),
                (30, "pause"), (40, "resume"), (50, "pause"), (60, "resume"), (70, "stop"),
            ]
            base = datetime(2026, 6, 10, 10, 0, 0)
            original_now = timer._now
            try:
                for minute, action in ticks:
                    timer._now = lambda m=minute: base + timedelta(minutes=m)
                    with redirect_stdout(io.StringIO()):
                        if action == "start":
                            timer.start_timer(start_args)
                        elif action == "pause":
                            timer.pause_timer(command_args)
                        elif action == "resume":
                            timer.resume_timer(command_args)
                        elif action == "stop":
                            timer.stop_timer(stop_args)
            finally:
                timer._now = original_now

            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            # Work intervals: 0-10, 20-30, 40-50, 60-70 = 40 minutes total.
            self.assertIn("elapsed:40m", text)
            self.assertFalse(os.path.exists(state_file))


def run_lifetxt_cli(*args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [sys.executable, "-m", "lifetxt"] + list(args),
        cwd=ROOT_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate()
    return (
        stdout.decode("utf-8"),
        stderr.decode("utf-8"),
        process.returncode,
    )
