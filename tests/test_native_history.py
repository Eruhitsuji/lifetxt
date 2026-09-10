import unittest

from lifetxt.native_history import (
    build_item_event,
    item_event_completeness,
    item_event_diagnostics,
    item_event_history_diagnostics,
    native_history_completeness,
    normalize_native_events,
)
from lifetxt.parser import parse_text
from lifetxt.progress_history import build_progress_event
from lifetxt.serializer import item_to_line
from lifetxt.ticket_activity import build_ticket_event, build_time_entry


REVISION = "a" * 64


class NativeItemEventTests(unittest.TestCase):
    def event(self, event_type="created", sequence=1, **payload):
        if not payload:
            payload = {
                "item_kind": "T",
                "item_title": "Task",
                "after_status": "[ ]",
            }
        return build_item_event(
            "task-1",
            event_type,
            "2026-09-10T10:00:00Z",
            sequence,
            "ITX-task-1-%06d" % sequence,
            REVISION,
            actor="me",
            source="cli",
            **payload
        )

    def test_builder_emits_stable_closed_envelope(self):
        event = self.event()
        self.assertEqual(["item_event"], event.details["record"])
        self.assertEqual(["IE-task-1-000001"], event.details["id"])
        self.assertEqual(["task-1"], event.details["parent"])
        self.assertEqual([], item_event_diagnostics(event))

    def test_builder_rejects_arbitrary_relation_and_schedule_fields(self):
        with self.assertRaises(ValueError):
            self.event("relation_added", relation="depends_on", target="task-2")
        with self.assertRaises(ValueError):
            self.event(
                "schedule_changed",
                field="do",
                before_missing=True,
                after="2026-09-11",
            )
        with self.assertRaises(ValueError):
            self.event("status_changed", before_status="[ ]", after_status="[/]", title="x")

    def test_validator_rejects_unknown_payload_and_invalid_missing_pair(self):
        event = self.event()
        event.details["custom"] = ["x"]
        self.assertIn("W264", [row.code for row in item_event_diagnostics(event)])
        schedule = self.event(
            "schedule_changed",
            field="due",
            before_missing=True,
            after="2026-09-11",
        )
        schedule.details["after_missing"] = ["true"]
        self.assertIn("W269", [row.code for row in item_event_diagnostics(schedule)])

    def test_history_detects_duplicate_gap_discontinuity_and_backwards_time(self):
        created = self.event()
        changed = self.event(
            "status_changed",
            sequence=3,
            before_status="[/]",
            after_status="[x]",
        )
        changed.details["at"] = ["2026-09-10T09:00:00Z"]
        duplicate = self.event()
        items, _ = parse_text(
            "[x] T Task id:task-1\n"
            + item_to_line(created)
            + "\n"
            + item_to_line(changed)
            + "\n"
            + item_to_line(duplicate)
            + "\n"
        )
        codes = [row.code for row in item_event_history_diagnostics(items)]
        self.assertIn("W272", codes)
        self.assertIn("W273", codes)
        self.assertIn("W274", codes)
        self.assertIn("W276", codes)

    def test_stream_without_creation_is_readable_but_partial(self):
        event = self.event(
            "status_changed",
            sequence=7,
            before_status="[ ]",
            after_status="[/]",
        )
        items, _ = parse_text("[/] T Task id:task-1\n" + item_to_line(event) + "\n")
        report = item_event_completeness(items, "task-1")
        self.assertEqual("partial", report["coverage"])
        self.assertFalse(report["complete"])
        self.assertEqual([], report["diagnostic_codes"])

    def test_complete_stream_requires_current_status_agreement(self):
        event = self.event()
        items, _ = parse_text("[ ] T Task id:task-1\n" + item_to_line(event) + "\n")
        self.assertTrue(item_event_completeness(items, "task-1")["complete"])
        items[0].status = "[x]"
        self.assertIn(
            "W277", [row.code for row in item_event_history_diagnostics(items)]
        )

    def test_completeness_is_reported_per_domain(self):
        event = self.event()
        items, _ = parse_text("[ ] T Task id:task-1\n" + item_to_line(event) + "\n")
        report = native_history_completeness(items, "task-1")
        self.assertTrue(report["item"]["complete"])
        self.assertEqual("none", report["progress"]["coverage"])
        self.assertFalse(report["ticket"]["complete"])
        self.assertEqual("none", report["time_entry"]["coverage"])


class NativeHistoryAdapterTests(unittest.TestCase):
    def test_adapters_retain_original_kind_and_id(self):
        item_event = build_item_event(
            "task-1",
            "created",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-1",
            REVISION,
            item_kind="T",
            item_title="Task",
            after_status="[ ]",
        )
        progress = build_progress_event(
            "task-1", None, "20%", "set", "2026-09-10T10:01:00Z", 1, "PTX-1", REVISION
        )
        ticket = build_ticket_event(
            "task-1", "comment", "me", "2026-09-10T10:02:00Z", 1, "TX-1", REVISION, body="hi"
        )
        time = build_time_entry(
            "task-1", "demo", "me", "development", "2026-09-10", "30m", 1, "EV-1", "2026-09-10T10:03:00Z"
        )
        rows = normalize_native_events([item_event, progress, ticket, time], "task-1")
        self.assertEqual(
            ["item_event", "progress_event", "ticket_event", "time_entry"],
            [row["record_kind"] for row in rows],
        )
        self.assertEqual(
            [
                "IE-task-1-000001",
                "PE-task-1-000001",
                "EV-task-1-000001",
                "TIME-task-1-000001",
            ],
            [row["record_id"] for row in rows],
        )
        self.assertEqual([True, True, True, True], [row["valid"] for row in rows])
