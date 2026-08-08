import contextlib
import datetime
import io
import os
import tempfile
import unittest

from lifetxt import config
from lifetxt import entrypoint
from lifetxt import extra_cli
from lifetxt.extra_common import _rank_key
from lifetxt.model import Item


SAMPLE = """[ ] T \"日本語 task\" id:t1 priority:A due:2026-07-20 project:alpha assignee:leo created:2026-07-01 elapsed:1h30m file:docs/readme.txt
[ ] T Blocked id:t2 depends_on:missing project:alpha assignee:leo
[x] T Dependency id:t3 done:2026-07-19 project:alpha assignee:leo elapsed:30m
[?] T Someday id:t4 created:2026-01-01 project:ideas
[/] T Today id:t5 do:2026-07-20 assignee:leo project:beta
[ ] E Meeting id:e1 from:2026-07-20T10:00+09:00 to:2026-07-20T11:00+09:00 loc:Room
"""


class RankKeyTests(unittest.TestCase):
    """Direct unit coverage for _rank_key, without going through the CLI."""

    TODAY = datetime.date(2026, 7, 20)

    def _item(self, priority=None, due=None, created=None, line=1):
        details = {}
        if priority is not None:
            details["priority"] = priority
        if due is not None:
            details["due"] = due
        if created is not None:
            details["created"] = created
        return Item(status="[ ]", kind="T", title="t", details=details, line=line)

    def test_overdue_item_ranks_ahead_of_higher_priority_not_yet_due_item(self):
        overdue = self._item(priority="C", due="2026-07-01")
        not_due_yet = self._item(priority="A", due="2026-08-01")
        keys = sorted(
            [not_due_yet, overdue], key=lambda item: _rank_key(item, self.TODAY)
        )
        self.assertIs(keys[0], overdue)
        self.assertIs(keys[1], not_due_yet)

    def test_item_due_today_is_not_overdue(self):
        due_today = self._item(due="2026-07-20")
        due_tomorrow = self._item(due="2026-07-21")
        self.assertEqual(_rank_key(due_today, self.TODAY)[0], 1)
        self.assertEqual(_rank_key(due_tomorrow, self.TODAY)[0], 1)
        keys = sorted(
            [due_tomorrow, due_today], key=lambda item: _rank_key(item, self.TODAY)
        )
        self.assertIs(keys[0], due_today)
        self.assertIs(keys[1], due_tomorrow)

    def test_item_with_no_due_date_is_not_overdue_and_sorts_after_present_due(self):
        no_due = self._item(priority="A")
        has_due = self._item(priority="A", due="2026-07-25")
        self.assertEqual(_rank_key(no_due, self.TODAY)[0], 1)
        keys = sorted([no_due, has_due], key=lambda item: _rank_key(item, self.TODAY))
        self.assertIs(keys[0], has_due)
        self.assertIs(keys[1], no_due)

    def test_ties_break_by_created_then_line(self):
        earlier_created = self._item(
            priority="A", due="2026-07-01", created="2026-06-01", line=10
        )
        later_created = self._item(
            priority="A", due="2026-07-01", created="2026-06-15", line=5
        )
        same_everything_later_line = self._item(
            priority="A", due="2026-07-01", created="2026-06-01", line=20
        )
        keys = sorted(
            [later_created, same_everything_later_line, earlier_created],
            key=lambda item: _rank_key(item, self.TODAY),
        )
        self.assertIs(keys[0], earlier_created)
        self.assertIs(keys[1], same_everything_later_line)
        self.assertIs(keys[2], later_created)


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

    def test_next_default_order_is_unchanged_without_rank(self):
        with_rank_flag_absent = self.run_extra(["next", self.path, "--format", "json"])
        # Priority A (t1) sorts ahead of blank priority (t5) under next's
        # existing default key; --rank must not be required to see this, and
        # must not change it when omitted.
        self.assertLess(
            with_rank_flag_absent.index('"id":"t1"'),
            with_rank_flag_absent.index('"id":"t5"'),
        )
        rank_false_explicit = self.run_extra(["next", self.path, "--format", "json"])
        self.assertEqual(with_rank_flag_absent, rank_false_explicit)

    def _write_convergence_fixture(self):
        path = os.path.join(self.tempdir.name, "converge.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Task id:c1\n"
                "[ ] D Deferred id:c2\n"
                "[ ] R Recurring id:c3\n"
                "[ ] H Habit id:c4\n"
                "[ ] E Event id:c5\n"
                '[ ] T "Someday tagged" id:c6 tag:someday\n'
                '[x] T "Dep done" id:c7\n'
                '[ ] T "Freed by closed dep" id:c8 depends_on:c7\n'
                '[ ] T "Dangling dep" id:c9 depends_on:does-not-exist\n'
            )
        return path

    def test_next_now_includes_deferred_recurring_and_habit_kinds(self):
        path = self._write_convergence_fixture()
        output = self.run_extra(["next", path, "--format", "json"])
        self.assertIn('"id":"c2"', output)
        self.assertIn('"id":"c3"', output)
        self.assertIn('"id":"c4"', output)
        self.assertNotIn('"id":"c5"', output)

    def test_next_now_excludes_someday_tagged_items_with_open_status(self):
        path = self._write_convergence_fixture()
        output = self.run_extra(["next", path, "--format", "json"])
        self.assertNotIn('"id":"c6"', output)

    def test_next_includes_item_once_its_dependency_is_closed(self):
        path = self._write_convergence_fixture()
        output = self.run_extra(["next", path, "--format", "json"])
        self.assertIn('"id":"c8"', output)

    def test_next_still_excludes_item_with_a_dangling_dependency(self):
        path = self._write_convergence_fixture()
        output = self.run_extra(["next", path, "--format", "json"])
        self.assertNotIn('"id":"c9"', output)

    def test_next_resolves_blocking_across_files(self):
        blocker_path = os.path.join(self.tempdir.name, "blocker.txt")
        blocked_path = os.path.join(self.tempdir.name, "blocked.txt")
        with open(blocker_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Blocker id:x1\n")
        with open(blocked_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Blocked id:x2 depends_on:x1\n")
        output = self.run_extra(
            ["next", blocker_path, blocked_path, "--format", "json"]
        )
        self.assertIn('"id":"x1"', output)
        self.assertNotIn('"id":"x2"', output)

    def _write_rank_fixture(self):
        path = os.path.join(self.tempdir.name, "rank.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Overdue id:r1 priority:C due:2000-01-01 created:2026-01-01 "
                "project:alpha assignee:leo context:office\n"
                "[ ] T NotDueYet id:r2 priority:A due:2099-01-01 created:2026-01-01 "
                "project:alpha assignee:leo context:office\n"
                "[ ] T NoDue id:r3 priority:A created:2026-01-01 "
                "project:beta assignee:sam context:home\n"
            )
        return path

    def test_next_rank_orders_overdue_items_first(self):
        path = self._write_rank_fixture()
        default_output = self.run_extra(["next", path, "--format", "json"])
        self.assertEqual(
            [default_output.index('"id":"%s"' % item) for item in ("r2", "r3", "r1")],
            sorted(
                default_output.index('"id":"%s"' % item) for item in ("r2", "r3", "r1")
            ),
        )
        ranked_output = self.run_extra(["next", path, "--rank", "--format", "json"])
        positions = [
            ranked_output.index('"id":"%s"' % item) for item in ("r1", "r2", "r3")
        ]
        self.assertEqual(positions, sorted(positions))

    def test_next_rank_reports_invalid_due_dates_instead_of_ranking_silently(self):
        path = os.path.join(self.tempdir.name, "invalid_due.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Bad id:b1 priority:A due:not-a-date\n"
                "[ ] T Good id:b2 priority:A due:2026-07-25\n"
            )
        with self.assertRaises(ValueError) as cm:
            extra_cli.main(["next", path, "--rank"])
        self.assertIn("b1", str(cm.exception))
        self.assertIn("not-a-date", str(cm.exception))

    def test_next_without_rank_tolerates_invalid_due_dates(self):
        path = os.path.join(self.tempdir.name, "invalid_due.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Bad id:b1 priority:A due:not-a-date\n")
        output = self.run_extra(["next", path, "--format", "json"])
        self.assertIn('"id":"b1"', output)

    def test_next_rank_selects_the_same_items_as_default(self):
        path = self._write_rank_fixture()
        default_output = self.run_extra(["next", path, "--format", "json"])
        ranked_output = self.run_extra(["next", path, "--rank", "--format", "json"])
        default_ids = {"r1", "r2", "r3"} & {
            item for item in ("r1", "r2", "r3") if '"id":"%s"' % item in default_output
        }
        ranked_ids = {"r1", "r2", "r3"} & {
            item for item in ("r1", "r2", "r3") if '"id":"%s"' % item in ranked_output
        }
        self.assertEqual(default_ids, ranked_ids)
        self.assertEqual(default_ids, {"r1", "r2", "r3"})

    def test_next_rank_applies_across_formats(self):
        path = self._write_rank_fixture()
        json_output = self.run_extra(["next", path, "--rank", "--format", "json"])
        life_output = self.run_extra(["next", path, "--rank", "--format", "life"])
        self.assertLess(json_output.index('"id":"r1"'), json_output.index('"id":"r2"'))
        self.assertLess(life_output.index("id:r1"), life_output.index("id:r2"))
        self.assertLess(life_output.index("id:r2"), life_output.index("id:r3"))

    def test_next_rank_composes_with_existing_options(self):
        path = self._write_rank_fixture()
        limited = self.run_extra(
            ["next", path, "--rank", "--limit", "1", "--format", "json"]
        )
        self.assertIn('"id":"r1"', limited)
        self.assertNotIn('"id":"r2"', limited)

        by_project = self.run_extra(
            ["next", path, "--rank", "--project", "beta", "--format", "json"]
        )
        self.assertIn('"id":"r3"', by_project)
        self.assertNotIn('"id":"r1"', by_project)

        by_user = self.run_extra(
            ["next", path, "--rank", "--user", "sam", "--format", "json"]
        )
        self.assertIn('"id":"r3"', by_user)
        self.assertNotIn('"id":"r1"', by_user)

        by_context = self.run_extra(
            ["next", path, "--rank", "--context", "home", "--format", "json"]
        )
        self.assertIn('"id":"r3"', by_context)
        self.assertNotIn('"id":"r1"', by_context)

        with tempfile.TemporaryDirectory() as outdir:
            out_path = os.path.join(outdir, "ranked.json")
            self.run_extra(["next", path, "--rank", "--format", "json", "-o", out_path])
            with open(out_path, encoding="utf-8") as handle:
                written = handle.read()
            self.assertIn('"id":"r1"', written)

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
