import contextlib
import datetime
import io
import os
import tempfile
import unittest

from lifetxt import config
from lifetxt import entrypoint
from lifetxt import extra_cli


SAMPLE = """[ ] T \"日本語 task\" id:t1 priority:A due:2026-07-20 project:alpha assignee:leo created:2026-07-01 elapsed:1h30m file:docs/readme.txt
[ ] T Blocked id:t2 depends_on:missing project:alpha assignee:leo
[x] T Dependency id:t3 done:2026-07-19 project:alpha assignee:leo elapsed:30m
[?] T Someday id:t4 created:2026-01-01 project:ideas
[/] T Today id:t5 do:2026-07-20 assignee:leo project:beta
[ ] E Meeting id:e1 from:2026-07-20T10:00+09:00 to:2026-07-20T11:00+09:00 loc:Room
"""


class ExtraCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tempdir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(SAMPLE)
        os.makedirs(os.path.join(self.tempdir.name, "docs"))
        with open(
            os.path.join(self.tempdir.name, "docs", "readme.txt"), "w", encoding="utf-8"
        ) as handle:
            handle.write("hello")

    def tearDown(self):
        self.tempdir.cleanup()

    def run_extra(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = extra_cli.main(argv)
        self.assertEqual(result, 0)
        return output.getvalue()

    def test_review_convenience_ranges(self):
        today = datetime.date(2026, 7, 20)
        self.assertEqual(
            entrypoint._review_selector_args(["review", "--last-week"], today),
            ["review", "--from", "2026-07-13", "--to", "2026-07-19"],
        )
        self.assertEqual(
            entrypoint._review_selector_args(["review", "--last-month"], today),
            ["review", "--month", "2026-06"],
        )
        self.assertEqual(
            entrypoint._review_selector_args(["review", "--year", "2025"], today),
            ["review", "--from", "2025-01-01", "--to", "2025-12-31"],
        )

    def test_config_init_extension_includes_editor(self):
        entrypoint._install_config_template_extension()
        self.assertIn("editor", config.config_template())

    def test_next_excludes_blocked_and_someday_items(self):
        output = self.run_extra(["next", self.path, "--format", "json"])
        self.assertIn('"id":"t1"', output)
        self.assertIn('"id":"t5"', output)
        self.assertNotIn('"id":"t2"', output)
        self.assertNotIn('"id":"t4"', output)

    def test_show_and_count_support_cjk_titles(self):
        output = self.run_extra(["show", "t1", self.path])
        self.assertIn("日本語 task", output)
        output = self.run_extra(["count", self.path, "--by", "project"])
        self.assertIn("alpha", output)
        self.assertIn("ideas", output)

    def test_invoice_and_workload_json(self):
        output = self.run_extra(
            [
                "invoice",
                self.path,
                "--from",
                "2026-07-01",
                "--to",
                "2026-07-31",
                "--default-rate",
                "1000",
                "--format",
                "json",
            ]
        )
        self.assertIn('"total":"2000.00"', output)
        output = self.run_extra(["who", self.path, "--workload", "--format", "json"])
        self.assertIn('"leo"', output)
        self.assertIn('"overdue"', output)

    def test_someday_review_and_standup(self):
        output = self.run_extra(["review", self.path, "--someday", "--days", "30"])
        self.assertIn("Someday", output)
        output = self.run_extra(
            [
                "standup",
                self.path,
                "--user",
                "leo",
                "--date",
                "2026-07-20",
                "--format",
                "json",
            ]
        )
        self.assertIn('"done_yesterday"', output)
        self.assertIn('"planned_today"', output)

    def test_to_ics_preserves_instant_and_event(self):
        output = self.run_extra(["to-ics", self.path])
        self.assertIn("BEGIN:VEVENT", output)
        self.assertIn("DTSTART:20260720T010000Z", output)
        self.assertIn("SUMMARY:Meeting", output)

    def test_todo_and_github_markdown_import(self):
        todo_path = os.path.join(self.tempdir.name, "todo.txt")
        with open(todo_path, "w", encoding="utf-8") as handle:
            handle.write("x 2026-07-19 2026-07-01 (A) Ship release +lifetxt @desk\n")
        output = self.run_extra(["from-todo", todo_path])
        self.assertIn("done:2026-07-19", output)
        self.assertIn("project:lifetxt", output)
        markdown_path = os.path.join(self.tempdir.name, "tasks.md")
        with open(markdown_path, "w", encoding="utf-8") as handle:
            handle.write("- [ ] Review #42 @alice\n  - [x] Merge follow-up\n")
        output = self.run_extra(["from-markdown", markdown_path, "--preset", "github"])
        self.assertIn("ref:github#42", output)
        self.assertIn("assignee:alice", output)
        self.assertIn("parent:md_", output)

    def test_attachment_open_dry_run_is_confined(self):
        output = self.run_extra(["files", self.path, "--open", "t1", "--dry-run"])
        self.assertEqual(
            output.strip(), os.path.join(self.tempdir.name, "docs", "readme.txt")
        )

    def test_powershell_completion(self):
        output = self.run_extra(["completion", "powershell"])
        self.assertIn("Register-ArgumentCompleter", output)
        self.assertIn("'next'", output)


if __name__ == "__main__":
    unittest.main()
