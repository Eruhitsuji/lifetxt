import datetime
import os
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt.command_center import command_center
from lifetxt.areas import area_list, area_show, collect_areas
from lifetxt.links import backlink_records
from lifetxt.inbox import stage_create


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

    def test_acknowledged_message_is_excluded_from_attention(self):
        items, _ = parse_text(
            SAMPLE + "[ ] M Acked sender:bob recipient:self body:hi ack:2026-07-20\n"
        )
        cc = command_center(items, {}, TODAY)
        self.assertNotIn("Acked", [r["title"] for r in cc["messages"]])
        self.assertEqual(["Ping"], [r["title"] for r in cc["messages"]])

    def test_actively_snoozed_message_is_excluded_from_attention(self):
        items, _ = parse_text(
            SAMPLE
            + "[ ] M Snoozed sender:bob recipient:self body:hi snooze_until:2026-07-26\n"
        )
        cc = command_center(items, {}, TODAY)
        self.assertNotIn("Snoozed", [r["title"] for r in cc["messages"]])

    def test_expired_snooze_message_still_shows(self):
        items, _ = parse_text(
            SAMPLE
            + "[ ] M Expired sender:bob recipient:self body:hi snooze_until:2026-07-24\n"
        )
        cc = command_center(items, {}, TODAY)
        self.assertIn("Expired", [r["title"] for r in cc["messages"]])

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

    def test_next_actions_reuses_the_shared_actionable_definition(self):
        from lifetxt.nextaction import next_action_items

        cc = self.cc()
        expected = [item.title for item in next_action_items(self.items)]
        self.assertEqual(expected, [r["title"] for r in cc["next_actions"]])
        # Deploy depends_on the still-open Design task, so it is blocked and
        # excluded; WaitingReply is status [?], never actionable.
        self.assertNotIn("Deploy", expected)
        self.assertNotIn("WaitingReply", expected)
        self.assertEqual(len(expected), cc["counts"]["next_actions"])

    def test_next_actions_limit_bounds_the_list_without_changing_order(self):
        unbounded = self.cc()["next_actions"]
        bounded = self.cc(next_actions_limit=1)["next_actions"]
        self.assertEqual(1, len(bounded))
        self.assertEqual(unbounded[0], bounded[0])

    def test_inbox_is_empty_when_no_proposals_are_staged(self):
        cc = self.cc()
        self.assertEqual(0, cc["inbox"]["total"])
        self.assertEqual(0, cc["inbox"]["pending_count"])
        self.assertEqual(0, cc["inbox"]["deferred_count"])
        self.assertEqual([], cc["inbox"]["pending"])
        self.assertEqual(0, cc["counts"]["inbox_pending"])

    def test_inbox_reports_pending_and_deferred_counts_and_bounded_summary(self):
        from lifetxt.inbox import defer

        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "proposals.json")
            config = {
                "inbox": {"proposals_file": store},
                "projects": {"web": {"default_area": "work"}},
            }
            for index in range(3):
                stage_create(config, "Idea %d" % index, source="manual")
            deferred = stage_create(config, "Later", source="mcp")
            defer(config, deferred["id"])

            cc = command_center(self.items, config, TODAY, inbox_limit=2)

            self.assertEqual(4, cc["inbox"]["total"])
            self.assertEqual(3, cc["inbox"]["pending_count"])
            self.assertEqual(1, cc["inbox"]["deferred_count"])
            self.assertEqual(3, cc["counts"]["inbox_pending"])
            # Bounded to inbox_limit even though 3 proposals are pending.
            self.assertEqual(2, len(cc["inbox"]["pending"]))
            for proposal in cc["inbox"]["pending"]:
                self.assertEqual({"id", "source", "created", "summary"}, set(proposal))
                self.assertTrue(proposal["summary"].startswith("Idea"))

    def test_inbox_pending_never_exposes_the_full_operational_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "proposals.json")
            config = {"inbox": {"proposals_file": store}}
            stage_create(config, "Idea", source="manual", details={"tag": "x"})

            cc = command_center(self.items, config, TODAY)

            proposal = cc["inbox"]["pending"][0]
            self.assertNotIn("changes", proposal)
            self.assertNotIn("expected_revision", proposal)
            self.assertNotIn("warnings", proposal)


TICKET_SAMPLE = """#! timezone: UTC
[ ] T Reviewed record:ticket ticket_status:review id:tk1 severity:low
[ ] T Critical record:ticket severity:critical id:tk2
[ ] T Stale record:ticket updated:2000-01-01 id:tk3
[ ] T Normal record:ticket severity:low id:tk4
[x] T Done record:ticket ticket_status:closed severity:critical id:tk5
[ ] T NotATicket id:tk6 severity:critical
"""


class TicketAttentionTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(TICKET_SAMPLE)

    def cc(self, **kwargs):
        return command_center(self.items, {}, TODAY, **kwargs)

    def test_review_status_ticket_is_flagged(self):
        cc = self.cc()
        row = next(r for r in cc["ticket_attention"] if r["title"] == "Reviewed")
        self.assertIn("review", row["reasons"])

    def test_high_severity_ticket_is_flagged(self):
        cc = self.cc()
        row = next(r for r in cc["ticket_attention"] if r["title"] == "Critical")
        self.assertIn("high_severity", row["reasons"])

    def test_stale_ticket_is_flagged(self):
        cc = self.cc()
        row = next(r for r in cc["ticket_attention"] if r["title"] == "Stale")
        self.assertIn("stale", row["reasons"])

    def test_ticket_matching_none_of_the_reasons_is_excluded(self):
        cc = self.cc()
        self.assertNotIn("Normal", [r["title"] for r in cc["ticket_attention"]])

    def test_terminal_ticket_is_excluded_even_if_high_severity(self):
        cc = self.cc()
        self.assertNotIn("Done", [r["title"] for r in cc["ticket_attention"]])

    def test_non_ticket_item_is_never_considered(self):
        cc = self.cc()
        self.assertNotIn("NotATicket", [r["title"] for r in cc["ticket_attention"]])

    def test_ticket_attention_count_matches_the_list(self):
        cc = self.cc()
        self.assertEqual(len(cc["ticket_attention"]), cc["counts"]["ticket_attention"])

    def test_configurable_stale_after_days_reaches_the_engine(self):
        # node_facts() uses the real clock for staleness (matching
        # ticket_project_report.py's own reference_time(None) behavior),
        # not the fixture TODAY constant, so this uses a real "yesterday"
        # to stay deterministic regardless of when the suite runs -- a
        # stale_after of 0 then makes it immediately stale, proving the
        # parameter is actually threaded through rather than always
        # falling back to the module default. "Yesterday" is computed from
        # reference_time(None) (UTC), the same clock node_facts() itself
        # compares against -- using the local wall-clock date instead
        # (#508) is flaky in any timezone ahead of UTC, where local
        # "yesterday" often still falls on the same UTC calendar day as
        # "now", making the computed age_days 0 instead of the intended 1.
        from lifetxt.ticket_project_values import reference_time

        yesterday = (
            reference_time(None).date() - datetime.timedelta(days=1)
        ).isoformat()
        items, _ = parse_text(
            "#! timezone: UTC\n"
            "[ ] T RecentlyUpdated record:ticket updated:%s severity:low id:tk9\n"
            % yesterday
        )
        default = command_center(items, {}, TODAY)
        stale_now = command_center(items, {}, TODAY, ticket_stale_after_days=0)
        self.assertEqual([], default["ticket_attention"])
        self.assertEqual(
            ["RecentlyUpdated"], [r["title"] for r in stale_now["ticket_attention"]]
        )

    def test_matches_direct_ticket_row_and_node_facts_calls(self):
        from lifetxt.temporal_context import node_facts
        from lifetxt.ticket_project_values import is_ticket, ticket_row

        cc = self.cc()
        row = next(r for r in cc["ticket_attention"] if r["title"] == "Critical")
        target = next(
            item
            for item in self.items
            if item.details.get("id") == ["tk2"] and is_ticket(item)
        )
        self.assertEqual("critical", ticket_row(target)["severity"])
        self.assertEqual([], node_facts(target, TODAY))
        self.assertEqual(row["reasons"], ["high_severity"])


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
