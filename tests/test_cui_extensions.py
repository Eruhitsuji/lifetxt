import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime

from lifetxt import completion, fzf_helper, git_hook, stats, timer, tui
from lifetxt.parser import parse_text


class CompletionTests(unittest.TestCase):
    def test_generates_completion_for_new_commands(self):
        script = completion.bash_completion()

        self.assertIn("timer", script)
        self.assertIn("stats", script)
        self.assertIn("git-hook", script)
        self.assertIn("--type", script)

    def test_prints_fish_install_instructions(self):
        text = completion.install_instructions("fish")

        self.assertIn("lifetxt.fish", text)
        self.assertIn("lifetxt completion fish", text)


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
            output = tui.render_dashboard(argparse.Namespace(paths=[path]))

        self.assertIn("TASKS (open)", output)
        self.assertIn("Write_Report", output)
