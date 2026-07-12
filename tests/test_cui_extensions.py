import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from unittest.mock import patch

from lifetxt import cli, completion, fzf_helper, git_hook, stats, timer, tui
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
