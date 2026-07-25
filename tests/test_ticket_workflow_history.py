import contextlib
import io
import json
import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt import entrypoint
from lifetxt.model import Item
from lifetxt.mutation import MutationConflict
from lifetxt.parser import parse_text
from lifetxt.ticket_activity import (
    build_ticket_event,
    build_time_entry,
    ticket_activity_report,
    validate_ticket_history,
)
from lifetxt.ticket_revision_writes import ticket_file_revision
from lifetxt.ticket_workflow import (
    apply_comment,
    apply_time,
    apply_transition,
    apply_watch,
    effective_workflow,
    transition_plan,
)


class TicketWorkflowHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        self.config = {
            "paths": [self.life],
            "write_file": self.life,
            "user": {"name": "alice"},
            "ticketing": {
                "activities": ["development", "review", "testing"],
            },
        }
        self.write_life(
            "[ ] T Bug record:ticket id:BUG-1 tracker:bug "
            "ticket_status:new priority:normal project:web\n"
        )
        self.write_config()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_life(self, text, binary=False):
        if binary:
            with open(self.life, "wb") as handle:
                handle.write(text)
        else:
            with open(self.life, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)

    def write_config(self):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle)

    def read_items(self):
        with open(self.life, encoding="utf-8", newline="") as handle:
            items, diagnostics = parse_text(
                handle.read(), id_key="id", check_ids=False, check_references=False
            )
        self.assertFalse(
            [row.to_dict() for row in diagnostics if row.severity == "error"],
            diagnostics,
        )
        return items

    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", self.config_path] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_default_workflow_has_reopen_and_resolution_contract(self):
        report = effective_workflow(self.config)
        self.assertTrue(report["valid"], report)
        self.assertIn("new", report["transitions"])
        self.assertEqual("reopened", report["transitions"]["new"]["event"])
        self.assertTrue(report["transitions"]["resolved"]["resolution_required"])

    def test_configured_role_required_field_and_comment_are_enforced(self):
        config = {
            "ticketing": {
                "statuses": {"approved": {"life_status": "[x]"}},
                "workflow": {
                    "transitions": {
                        "approved": {
                            "from": ["new"],
                            "roles": ["manager"],
                            "required_fields": ["reviewer"],
                            "comment_required": True,
                            "resolution_required": True,
                            "event": "closed",
                        }
                    }
                },
            }
        }
        item = Item(
            "[ ]",
            "T",
            "Bug",
            OrderedDict(
                (
                    ("record", ["ticket"]),
                    ("id", ["BUG-1"]),
                    ("tracker", ["bug"]),
                    ("ticket_status", ["new"]),
                )
            ),
        )
        with self.assertRaises(ValueError):
            transition_plan(
                item,
                "approved",
                config=config,
                role="developer",
                comment="approved",
                resolution="done",
                extra_updates={"reviewer": "alice"},
            )
        with self.assertRaises(ValueError):
            transition_plan(
                item,
                "approved",
                config=config,
                role="manager",
                comment=None,
                resolution="done",
                extra_updates={"reviewer": "alice"},
            )
        plan = transition_plan(
            item,
            "approved",
            config=config,
            role="manager",
            comment="approved",
            resolution="done",
            extra_updates={"reviewer": "alice"},
        )
        self.assertEqual("[x]", plan["life_status"])
        self.assertEqual("approved", plan["to"])

    def test_transition_commits_ticket_and_event_in_one_revision(self):
        revision = ticket_file_revision(self.life)
        result = apply_transition(
            self.life,
            "BUG-1",
            "in_progress",
            "alice",
            "administrator",
            revision,
            config=self.config,
            at="2026-07-25T10:00:00+09:00",
            transaction_id="TX-TRANSITION-1",
        )
        self.assertNotEqual(revision, result["revision_after"])
        self.assertEqual("transition", result["event"]["event"])
        self.assertEqual("TX-TRANSITION-1", result["transaction_id"])

        report = ticket_activity_report(self.read_items(), "BUG-1", self.config)
        self.assertEqual("in_progress", report["ticket"]["summary"]["ticket_status"])
        self.assertEqual(1, len(report["events"]))
        self.assertEqual("2026-07-25T01:00:00Z", report["events"][0]["at"])
        self.assertTrue(report["events"][0]["changes"])

        with self.assertRaises(MutationConflict):
            apply_transition(
                self.life,
                "BUG-1",
                "review",
                "alice",
                "administrator",
                revision,
                config=self.config,
                at="2026-07-25T10:05:00+09:00",
            )

    def test_resolution_and_reopen_append_history(self):
        revision = ticket_file_revision(self.life)
        first = apply_transition(
            self.life,
            "BUG-1",
            "in_progress",
            "alice",
            "administrator",
            revision,
            config=self.config,
            at="2026-07-25T01:00:00Z",
        )
        with self.assertRaises(ValueError):
            apply_transition(
                self.life,
                "BUG-1",
                "resolved",
                "alice",
                "administrator",
                first["revision_after"],
                config=self.config,
                at="2026-07-25T02:00:00Z",
            )
        second = apply_transition(
            self.life,
            "BUG-1",
            "resolved",
            "alice",
            "administrator",
            first["revision_after"],
            config=self.config,
            resolution="fixed",
            comment="verified",
            at="2026-07-25T02:00:00Z",
        )
        self.assertEqual("closed", second["event"]["event"])
        third = apply_transition(
            self.life,
            "BUG-1",
            "new",
            "alice",
            "administrator",
            second["revision_after"],
            config=self.config,
            comment="regression",
            at="2026-07-25T03:00:00Z",
        )
        self.assertEqual("reopened", third["event"]["event"])
        report = ticket_activity_report(self.read_items(), "BUG-1", self.config)
        self.assertEqual("new", report["ticket"]["summary"]["ticket_status"])
        self.assertIsNone(report["ticket"]["resolution"])
        self.assertEqual(["transition", "closed", "reopened"], [r["event"] for r in report["events"]])

    def test_comment_watch_and_unwatch_have_deterministic_sequences(self):
        revision = ticket_file_revision(self.life)
        comment = apply_comment(
            self.life,
            "BUG-1",
            "Investigating",
            "alice",
            revision,
            config=self.config,
            at="2026-07-25T01:00:00Z",
            transaction_id="TX-COMMENT",
        )
        watched = apply_watch(
            self.life,
            "BUG-1",
            "bob",
            "alice",
            comment["revision_after"],
            config=self.config,
            at="2026-07-25T01:01:00Z",
        )
        unwatched = apply_watch(
            self.life,
            "BUG-1",
            "bob",
            "alice",
            watched["revision_after"],
            add=False,
            config=self.config,
            at="2026-07-25T01:02:00Z",
        )
        report = ticket_activity_report(self.read_items(), "BUG-1", self.config)
        self.assertEqual([1, 2, 3], [row["sequence"] for row in report["events"]])
        self.assertEqual(
            ["comment", "watch_added", "watch_removed"],
            [row["event"] for row in report["events"]],
        )
        self.assertEqual(unwatched["revision_after"], ticket_file_revision(self.life))
        self.assertEqual([], report["ticket"]["summary"]["watchers"])

    def test_time_correction_supersedes_referenced_entry(self):
        revision = ticket_file_revision(self.life)
        first = apply_time(
            self.life,
            "BUG-1",
            "2h",
            "alice",
            "development",
            revision,
            config=self.config,
            date="2026-07-25",
            comment="initial estimate",
            at="2026-07-25T04:00:00Z",
        )
        second = apply_time(
            self.life,
            "BUG-1",
            "90m",
            "alice",
            "development",
            first["revision_after"],
            config=self.config,
            date="2026-07-25",
            comment="corrected",
            corrects=first["time_entry"]["id"],
            at="2026-07-25T04:01:00Z",
        )
        report = ticket_activity_report(self.read_items(), "BUG-1", self.config)
        self.assertEqual(5400, report["time"]["authoritative_seconds"])
        self.assertEqual(
            [second["time_entry"]["id"]],
            report["time"]["effective_entry_ids"],
        )
        self.assertEqual(
            [first["time_entry"]["id"]],
            report["time"]["superseded_entry_ids"],
        )
        before = ticket_file_revision(self.life)
        with self.assertRaises(ValueError):
            apply_time(
                self.life,
                "BUG-1",
                "30m",
                "alice",
                "review",
                before,
                config=self.config,
                corrects="TIME-MISSING",
                at="2026-07-25T04:02:00Z",
            )
        self.assertEqual(before, ticket_file_revision(self.life))

    def test_history_validation_detects_id_sequence_transaction_and_correction_problems(self):
        ticket = Item(
            "[ ]",
            "T",
            "Bug",
            {
                "record": ["ticket"],
                "id": ["BUG-1"],
                "tracker": ["bug"],
                "ticket_status": ["new"],
            },
        )
        event1 = build_ticket_event(
            "BUG-1", "comment", "alice", "2026-07-25T00:00:00Z",
            1, "TX-1", "a" * 64, body="one"
        )
        event3 = build_ticket_event(
            "BUG-1", "comment", "alice", "2026-07-25T00:00:01Z",
            3, "TX-1", "a" * 64, body="three"
        )
        # Deliberately violate the canonical id independently of the sequence gap.
        event3.details["id"] = ["EV-WRONG"]
        time_entry = build_time_entry(
            "BUG-1", "web", "alice", "development", "2026-07-25",
            "1h", 1, "EV-MISSING", "2026-07-25T00:00:02Z",
            corrects="TIME-MISSING",
        )
        codes = {
            row["code"]
            for row in validate_ticket_history(
                [ticket, event1, event3, time_entry], config=self.config
            )
        }
        self.assertTrue({"TK032", "TK034", "TK035", "TK037", "TK039"}.issubset(codes))

    def test_crlf_and_dry_run_preserve_authoritative_bytes(self):
        self.write_life(
            b"[ ] T Bug record:ticket id:BUG-1 tracker:bug "
            b"ticket_status:new priority:normal project:web\r\n",
            binary=True,
        )
        revision = ticket_file_revision(self.life)
        preview = apply_comment(
            self.life,
            "BUG-1",
            "preview",
            "alice",
            revision,
            config=self.config,
            at="2026-07-25T00:00:00Z",
            dry_run=True,
        )
        self.assertEqual(revision, ticket_file_revision(self.life))
        self.assertNotEqual(revision, preview["revision_after"])
        applied = apply_comment(
            self.life,
            "BUG-1",
            "committed",
            "alice",
            revision,
            config=self.config,
            at="2026-07-25T00:00:00Z",
        )
        with open(self.life, "rb") as handle:
            data = handle.read()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertEqual(applied["revision_after"], ticket_file_revision(self.life))

    def test_cli_workflow_transition_activity_and_stale_conflict(self):
        code, stdout, stderr = self.run_cli(["ticket", "workflow", "--format", "json"])
        self.assertEqual(0, code, stderr)
        self.assertIn("transitions", json.loads(stdout))

        revision = ticket_file_revision(self.life)
        code, stdout, stderr = self.run_cli(
            [
                "ticket", "transition", "BUG-1", "in_progress",
                "--revision", revision,
                "--at", "2026-07-25T00:00:00Z",
                "--json",
            ]
        )
        self.assertEqual(0, code, stderr)
        payload = json.loads(stdout)
        self.assertEqual("transition", payload["event"]["event"])

        code, stdout, stderr = self.run_cli(
            [
                "ticket", "comment", "BUG-1", "stale",
                "--revision", revision,
                "--at", "2026-07-25T00:01:00Z",
            ]
        )
        self.assertEqual(1, code)
        self.assertIn("conflict", stderr.lower())

        code, stdout, stderr = self.run_cli(
            ["ticket", "activity", "BUG-1", "--format", "json"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(1, len(json.loads(stdout)["events"]))


if __name__ == "__main__":
    unittest.main()
