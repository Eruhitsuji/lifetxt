import datetime
import unittest

from lifetxt.parser import parse_text
from lifetxt.command_center import command_center
from lifetxt.areas import area_list, area_show, collect_areas
from lifetxt.links import backlink_records


TODAY = datetime.date(2026, 7, 24)

SAMPLE = """#! timezone: UTC
[ ] T Design project:web assignee:alice due:2026-07-01 id:T-1
[ ] T Deploy project:web depends_on:T-1 id:T-2
[ ] T DueToday project:web due:2026-07-24
[ ] T Soon project:web due:2026-07-26
[?] T WaitingReply project:web
[ ] T Idea
[ ] H Workout project:gym
[N] N Risk1 record:risk project:web severity:high state:open
[ ] M Ping sender:bob recipient:self body:hi
"""


class CommandCenterTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def cc(self, **kwargs):
        return command_center(
            self.items, {"projects": {"web": {"default_area": "work"}}}, TODAY, **kwargs
        )

    def test_overdue_due_today_and_upcoming_split(self):
        cc = self.cc()
        self.assertEqual(["Design"], [r["title"] for r in cc["overdue"]])
        self.assertEqual(["DueToday"], [r["title"] for r in cc["due_today"]])
        self.assertEqual(["Soon"], [r["title"] for r in cc["upcoming"]])

    def test_blocked_and_waiting(self):
        cc = self.cc()
        self.assertEqual(["Deploy"], [r["title"] for r in cc["blocked"]])
        self.assertEqual(["WaitingReply"], [r["title"] for r in cc["waiting"]])

    def test_captures_are_untriaged_tasks(self):
        cc = self.cc()
        self.assertEqual(["Idea"], [r["title"] for r in cc["captures"]])

    def test_habits_and_messages(self):
        cc = self.cc()
        self.assertEqual(["Workout"], [r["title"] for r in cc["habits"]])
        self.assertEqual(["Ping"], [r["title"] for r in cc["messages"]])

    def test_message_person_scope(self):
        self.assertEqual(1, self.cc(person="self")["counts"]["messages"])
        self.assertEqual(0, self.cc(person="carol")["counts"]["messages"])

    def test_project_attention_flags_unhealthy(self):
        cc = self.cc()
        names = [p["name"] for p in cc["project_attention"]]
        self.assertIn("web", names)

    def test_reference_date_and_counts_present(self):
        cc = self.cc()
        self.assertEqual("2026-07-24", cc["reference_date"])
        self.assertEqual(1, cc["counts"]["overdue"])

    def test_horizon_controls_upcoming(self):
        # Narrowing the horizon to 1 day drops the 2026-07-26 task.
        cc = command_center(self.items, {}, TODAY, horizon_days=1)
        self.assertEqual([], [r["title"] for r in cc["upcoming"]])

    def test_safety_reports_config_problems(self):
        cc = command_center(self.items, {"config_version": 99}, TODAY)
        self.assertFalse(cc["safety"]["ok"])


class AreaTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)
        self.config = {
            "projects": {
                "web": {"default_area": "work"},
                "gym": {"default_area": "health"},
            }
        }

    def test_area_list_groups_by_project_default(self):
        rows = {r["name"]: r for r in area_list(self.items, self.config)}
        self.assertIn("work", rows)
        self.assertIn("health", rows)
        self.assertIn("(unassigned)", rows)

    def test_area_progress_counts_tasks(self):
        rows = {r["name"]: r for r in area_list(self.items, self.config)}
        # web tasks (T-1, T-2, DueToday, Soon, WaitingReply) land in work.
        self.assertGreaterEqual(rows["work"]["task_total"], 4)

    def test_area_show_lists_projects_and_open_items(self):
        summary = area_show(self.items, self.config, "work")
        self.assertIn("web", summary["projects"])
        self.assertTrue(summary["open_items"])

    def test_unknown_area_raises(self):
        with self.assertRaises(ValueError):
            area_show(self.items, self.config, "nope")

    def test_explicit_area_detail_wins(self):
        items, _ = parse_text("#! timezone: UTC\n[ ] T X project:web area:home\n")
        areas = collect_areas(items, {"projects": {"web": {"default_area": "work"}}})
        self.assertIn("home", areas)


class BacklinkTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_backlinks_find_incoming_references(self):
        records = backlink_records(self.items, "T-1")
        self.assertEqual(1, len(records))
        self.assertEqual("depends_on", records[0]["relation"])
        self.assertEqual("T-2", records[0]["source_id"])

    def test_no_backlinks_returns_empty(self):
        self.assertEqual([], backlink_records(self.items, "T-9"))


if __name__ == "__main__":
    unittest.main()
