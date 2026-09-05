"""CLI text-output coverage for `lifetxt today`'s ticket_attention section (#499)
and the #627 daily-hub restructuring (NOW/ATTENTION/TODAY/NEXT ACTIONS/
BLOCKED/HABITS/INBOX) and --saved-view/--area personalization scope.
"""

import datetime
import json
import os
import tempfile
import unittest

from tests.test_lifetxt import normalize_newlines, run_cli


SAMPLE = (
    "#! timezone: UTC\n"
    "[ ] T Reviewed record:ticket ticket_status:review id:tk1 severity:low\n"
    "[ ] T Normal record:ticket severity:low id:tk2\n"
)


class TodayCliTicketAttentionTests(unittest.TestCase):
    def _write_source(self, temp_dir, text=SAMPLE):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_text_output_lists_tickets_needing_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertIn("Tickets needing attention (1):", stdout)
            self.assertIn("Reviewed: review", stdout)
            # "Normal" has no due:/project:/assignee: either, so it
            # legitimately appears under Captures -- only the
            # ticket_attention row format ("status title: reasons") is
            # asserted absent here.
            self.assertNotIn("Normal:", stdout)

    def test_text_output_omits_the_section_when_nothing_qualifies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir, "#! timezone: UTC\n[ ] T Plain record:ticket severity:low\n"
            )
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("Tickets needing attention", stdout)

    def test_json_output_includes_ticket_attention(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src, "--json")
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(
                ["Reviewed"], [r["title"] for r in data["ticket_attention"]]
            )
            self.assertEqual(1, data["counts"]["ticket_attention"])


def _hub_sample():
    """Build a fixture relative to the real "today" `lifetxt today` sees, so
    these tests stay correct regardless of the wall-clock date they run on."""
    today = datetime.date.today()
    overdue = (today - datetime.timedelta(days=5)).isoformat()
    return (
        "#! timezone: UTC\n"
        "[/] S self state:focus from:%sT08:00\n"
        "[ ] E Team_meeting at:09:00 on:%s\n"
        "[ ] T Overdue_report due:%s project:lifetxt id:t1\n"
        "[ ] T Configure_DNS project:lifetxt id:t2\n"
        "[ ] T Deploy_website project:lifetxt depends_on:t2\n"
        "[ ] H Exercise\n" % (today.isoformat(), today.isoformat(), overdue)
    )


class TodayHubStructureTests(unittest.TestCase):
    """Covers #627's NOW/ATTENTION/TODAY/NEXT ACTIONS/BLOCKED/HABITS/INBOX
    daily-hub restructuring of the text renderer."""

    def _write_source(self, temp_dir, text=None):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(_hub_sample() if text is None else text)
        return path

    def test_text_output_uses_the_documented_hub_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            for heading in (
                "NOW",
                "ATTENTION",
                "TODAY",
                "NEXT ACTIONS",
                "BLOCKED",
                "HABITS",
            ):
                self.assertIn("\n%s\n" % heading, stdout)

    def test_now_shows_active_status_and_today_shows_events(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertIn("self: focus", stdout)
            self.assertIn("Team_meeting", stdout)

    def test_attention_row_carries_a_deterministic_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertIn("days overdue", stdout)

    def test_overdue_item_is_not_duplicated_under_next_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            # Overdue_report is actionable (open, unblocked) and therefore
            # already listed under ATTENTION; NEXT ACTIONS must not repeat it.
            next_actions_block = stdout.split("\nNEXT ACTIONS\n", 1)[1]
            next_actions_block = next_actions_block.split("\n\n", 1)[0]
            self.assertNotIn("Overdue_report", next_actions_block)
            self.assertIn("Configure_DNS", next_actions_block)

    def test_habit_is_not_duplicated_under_next_actions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            next_actions_block = stdout.split("\nNEXT ACTIONS\n", 1)[1]
            next_actions_block = next_actions_block.split("\n\n", 1)[0]
            self.assertNotIn("Exercise", next_actions_block)
            self.assertIn("\nHABITS\n", stdout)
            habits_block = stdout.split("\nHABITS\n", 1)[1]
            self.assertIn("Exercise", habits_block)

    def test_blocked_task_is_listed_under_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            blocked_block = stdout.split("\nBLOCKED\n", 1)[1].split("\n\n", 1)[0]
            self.assertIn("Deploy_website", blocked_block)

    def test_upcoming_item_not_already_shown_elsewhere_still_renders(self):
        soon = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "#! timezone: UTC\n"
                    "[?] T Waiting_and_soon due:%s project:lifetxt\n" % soon
                )
            stdout, stderr, code = run_cli("today", path)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertIn("Upcoming (3d)", stdout)
            self.assertIn("Waiting_and_soon", stdout.split("Upcoming (3d)", 1)[1])

    def test_upcoming_item_already_shown_under_next_actions_is_not_repeated(self):
        soon = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "life.txt")
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    "#! timezone: UTC\n"
                    "[ ] T Soon_actionable due:%s project:lifetxt\n" % soon
                )
            stdout, stderr, code = run_cli("today", path)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            next_actions_block = stdout.split("\nNEXT ACTIONS\n", 1)[1]
            next_actions_block = next_actions_block.split("\n\n", 1)[0]
            self.assertIn("Soon_actionable", next_actions_block)
            self.assertNotIn("Upcoming (3d)", stdout)


class TodayProgressDisplayTests(unittest.TestCase):
    """Covers #649: `progress:` shown in Today's human-readable listings,
    with no change to records that carry no `progress:` detail."""

    def _write_source(self, temp_dir, text):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_overdue_task_with_percentage_progress_shows_it_in_attention(self):
        overdue = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir,
                "#! timezone: UTC\n[ ] T Report due:%s progress:40%%\n" % overdue,
            )
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            attention_block = stdout.split("\nATTENTION\n", 1)[1].split("\n\n", 1)[0]
            self.assertIn("progress:40%", attention_block)

    def test_next_action_with_fraction_progress_shows_derived_percentage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir,
                "#! timezone: UTC\n[ ] T Experiment project:x progress:3/10\n",
            )
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            next_actions_block = stdout.split("\nNEXT ACTIONS\n", 1)[1]
            next_actions_block = next_actions_block.split("\n\n", 1)[0]
            self.assertIn("progress:3/10 (30%)", next_actions_block)

    def test_record_without_progress_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(
                temp_dir, "#! timezone: UTC\n[ ] T Plain_task project:x\n"
            )
            stdout, stderr, code = run_cli("today", src)
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            self.assertNotIn("progress:", stdout)


class TodayScopeCliTests(unittest.TestCase):
    """Covers #627 Phase 4 personalization: --saved-view / --area."""

    def _write_source(self, temp_dir):
        path = os.path.join(temp_dir, "life.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "#! timezone: UTC\n"
                "[ ] T Home_task project:home area:home\n"
                "[ ] T Work_task project:work area:work\n"
            )
        return path

    def test_area_narrows_the_report_and_annotates_the_header(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src, "--area", "home", "--json")
            stdout = normalize_newlines(stdout)
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(["Home_task"], [r["title"] for r in data["next_actions"]])

    def test_unknown_area_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli("today", src, "--area", "nope")
            stdout = normalize_newlines(stdout)
            self.assertEqual(1, code)
            self.assertIn("Unknown area", stderr)

    def test_saved_view_narrows_the_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            cfg = os.path.join(temp_dir, ".lifetxt.json")
            with open(cfg, "w", encoding="utf-8") as handle:
                json.dump({"saved_views": {"home": {"query": "area:home"}}}, handle)
            stdout, stderr, code = run_cli(
                "--config", cfg, "today", src, "--saved-view", "home", "--json"
            )
            self.assertEqual(0, code, stderr)
            data = json.loads(stdout)
            self.assertEqual(["Home_task"], [r["title"] for r in data["next_actions"]])

    def test_saved_view_and_area_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src = self._write_source(temp_dir)
            stdout, stderr, code = run_cli(
                "today", src, "--saved-view", "a", "--area", "b"
            )
            self.assertNotEqual(0, code)
            self.assertIn("not allowed with argument", stderr)


if __name__ == "__main__":
    unittest.main()
