import json
import os
import tempfile
import unittest

from lifetxt.native_history import build_item_event
from lifetxt.native_timeline import MAX_LIMIT, native_timeline
from lifetxt.parser import parse_text
from lifetxt.progress_history import build_progress_event
from lifetxt.serializer import item_to_line
from lifetxt.ticket_activity import build_ticket_event
from tests.test_lifetxt import run_cli


REVISION = "a" * 64


def _fixture():
    created = build_item_event(
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
    completed = build_item_event(
        "task-1",
        "completed",
        "2026-09-10T12:00:00Z",
        2,
        "ITX-2",
        REVISION,
        before_status="[ ]",
        after_status="[x]",
    )
    progress = build_progress_event(
        "task-1",
        None,
        "20%",
        "set",
        "2026-09-10T11:00:00Z",
        1,
        "PTX-1",
        REVISION,
    )
    text = (
        "[x] T Task id:task-1 progress:20%\n"
        + item_to_line(completed)
        + "\n"
        + item_to_line(progress)
        + "\n"
        + item_to_line(created)
        + "\n"
    )
    return parse_text(text)[0]


class NativeTimelineTests(unittest.TestCase):
    def test_normalizes_and_orders_mixed_native_records_deterministically(self):
        result = native_timeline(_fixture(), "task-1")
        self.assertEqual("temporal-timeline-v1", result["schema"])
        self.assertFalse(result["git_composed"])
        self.assertEqual(
            ["created", "progress_set", "completed"],
            [row["event"] for row in result["events"]],
        )
        self.assertEqual(
            ["item_event", "progress_event", "item_event"],
            [row["record_kind"] for row in result["events"]],
        )
        self.assertEqual("IE-task-1-000001", result["events"][0]["record_id"])
        self.assertTrue(result["complete"])

    def test_limit_is_bounded_and_reports_truncation(self):
        result = native_timeline(_fixture(), "task-1", limit=1)
        self.assertEqual(1, len(result["events"]))
        self.assertTrue(result["bounds"]["truncated"])
        self.assertIn("event_limit_truncated", result["limitations"])
        with self.assertRaises(ValueError):
            native_timeline(_fixture(), "task-1", limit=MAX_LIMIT + 1)

    def test_filters_are_inclusive_anded_and_run_before_limit(self):
        result = native_timeline(
            _fixture(),
            "task-1",
            since="2026-09-10T10:30:00+00:00",
            until="2026-09-10T12:00:00Z",
            limit=1,
        )
        self.assertEqual(["progress_set"], [row["event"] for row in result["events"]])
        self.assertEqual(2, result["bounds"]["total_valid_events"])
        self.assertTrue(result["bounds"]["truncated"])
        self.assertTrue(result["completeness"]["item"]["complete"])

    def test_event_filter_keeps_original_chronological_order(self):
        result = native_timeline(_fixture(), "task-1", event="completed")
        self.assertEqual(["completed"], [row["event"] for row in result["events"]])
        self.assertEqual(1, result["bounds"]["total_valid_events"])
        self.assertTrue(result["complete"])

    def test_invalid_filter_values_are_rejected_deterministically(self):
        with self.assertRaisesRegex(ValueError, "UTC offset"):
            native_timeline(_fixture(), "task-1", since="2026-09-10T10:00:00")
        with self.assertRaisesRegex(ValueError, "Unknown Timeline event"):
            native_timeline(_fixture(), "task-1", event="invented")
        with self.assertRaisesRegex(ValueError, "since must not be after until"):
            native_timeline(
                _fixture(),
                "task-1",
                since="2026-09-11T00:00:00Z",
                until="2026-09-10T00:00:00Z",
            )

    def test_malformed_event_is_separated_with_diagnostics(self):
        items = _fixture()
        malformed = build_item_event(
            "task-1",
            "schedule_changed",
            "2026-09-10T13:00:00Z",
            3,
            "ITX-3",
            REVISION,
            field="due",
            before_missing=True,
            after="2026-09-12",
        )
        malformed.details["at"] = ["not-a-time"]
        items.append(malformed)
        result = native_timeline(items, "task-1")
        self.assertEqual(1, len(result["invalid_events"]))
        self.assertIn("W265", [row["code"] for row in result["diagnostics"]])
        self.assertFalse(result["complete"])

    def test_missing_creation_remains_readable_partial(self):
        event = build_item_event(
            "task-1",
            "status_changed",
            "2026-09-10T10:00:00Z",
            8,
            "ITX-8",
            REVISION,
            before_status="[ ]",
            after_status="[/]",
        )
        items, _ = parse_text("[/] T Task id:task-1\n" + item_to_line(event) + "\n")
        result = native_timeline(items, "task-1")
        self.assertEqual("partial", result["completeness"]["item"]["coverage"])
        self.assertFalse(result["complete"])

    def test_ticket_specialization_retains_identity_but_does_not_claim_complete(self):
        ticket = build_ticket_event(
            "TK-1", "created", "me", "2026-09-10T10:00:00Z", 1, "TX-1", REVISION
        )
        items, _ = parse_text(
            "[ ] T Ticket record:ticket id:TK-1 ticket_status:new\n"
            + item_to_line(ticket)
            + "\n"
        )
        result = native_timeline(items, "TK-1")
        self.assertEqual("ticket_event", result["events"][0]["record_kind"])
        self.assertEqual("EV-TK-1-000001", result["events"][0]["record_id"])
        self.assertTrue(result["completeness"]["ticket"]["complete"])


class NativeTimelineCliTests(unittest.TestCase):
    def test_text_and_json_share_the_same_bounded_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for item in _fixture():
                    handle.write(item_to_line(item) + "\n")
            stdout, stderr, code = run_cli("timeline", "task-1", path, "--json")
            self.assertEqual(0, code, stderr)
            result = json.loads(stdout)
            self.assertEqual("temporal-timeline-v1", result["schema"])
            stdout, stderr, code = run_cli("timeline", "task-1", path, "--limit", "1")
            self.assertEqual(0, code, stderr)
            self.assertIn("Native Timeline for task-1", stdout)
            self.assertIn(result["events"][0]["record_id"], stdout)

    def test_unknown_id_fails_loudly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Task id:task-1\n")
            _stdout, stderr, code = run_cli("timeline", "missing", path)
            self.assertNotEqual(0, code)
            self.assertIn("Expected exactly one item", stderr)

    def test_cli_filters_share_the_domain_result_and_reject_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for item in _fixture():
                    handle.write(item_to_line(item) + "\n")
            stdout, stderr, code = run_cli(
                "timeline",
                "task-1",
                path,
                "--since",
                "2026-09-10T10:30:00Z",
                "--event",
                "progress_set",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            self.assertEqual(
                ["progress_set"],
                [row["event"] for row in json.loads(stdout)["events"]],
            )
            _stdout, stderr, code = run_cli(
                "timeline", "task-1", path, "--event", "unknown"
            )
            self.assertNotEqual(0, code)
            self.assertIn("Unknown Timeline event", stderr)


class NativeTimelineAsOfCliTests(unittest.TestCase):
    def test_as_of_renders_alongside_the_event_list_in_text_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for item in _fixture():
                    handle.write(item_to_line(item) + "\n")
            stdout, stderr, code = run_cli(
                "timeline",
                "task-1",
                path,
                "--as-of",
                "2026-09-10T11:00:00Z",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            result = json.loads(stdout)
            self.assertEqual("temporal-timeline-v1", result["schema"])
            self.assertIn("events", result)
            as_of = result["semantic_as_of"]
            self.assertEqual("semantic-as-of-v1", as_of["schema"])
            self.assertEqual("known", as_of["fields"]["status"]["state"])
            self.assertEqual("[ ]", as_of["fields"]["status"]["value"])
            self.assertEqual("unavailable", as_of["fields"]["due"]["state"])
            stdout, stderr, code = run_cli(
                "timeline", "task-1", path, "--as-of", "2026-09-10T11:00:00Z"
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Native Timeline for task-1", stdout)
            self.assertIn("As of 2026-09-10T11:00:00Z:", stdout)
            self.assertIn("status: [ ] [known]", stdout)

    def test_invalid_as_of_fails_loudly_like_show_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Task id:task-1\n")
            _stdout, stderr, code = run_cli(
                "timeline", "task-1", path, "--as-of", "not-a-timestamp"
            )
            self.assertNotEqual(0, code)
            self.assertIn("--as-of must be an offset-aware RFC3339 timestamp", stderr)

    def test_domain_with_no_event_coverage_reports_unavailable_not_current_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[x] T Task id:task-1 due:2026-09-20\n")
            stdout, stderr, code = run_cli(
                "timeline",
                "task-1",
                path,
                "--as-of",
                "2026-09-10T11:00:00Z",
                "--json",
            )
            self.assertEqual(0, code, stderr)
            due = json.loads(stdout)["semantic_as_of"]["fields"]["due"]
            self.assertEqual("unavailable", due["state"])
            self.assertIsNone(due["value"])

    def test_as_of_cannot_combine_with_summary_or_compare_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("[ ] T Task id:task-1\n")
            _stdout, stderr, code = run_cli(
                "timeline",
                "task-1",
                path,
                "--as-of",
                "2026-09-10T11:00:00Z",
                "--summary",
            )
            self.assertNotEqual(0, code)
            self.assertIn("--as-of cannot be combined", stderr)

    def test_omitting_as_of_leaves_output_unaffected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "life.txt")
            with open(path, "w", encoding="utf-8") as handle:
                for item in _fixture():
                    handle.write(item_to_line(item) + "\n")
            stdout, stderr, code = run_cli("timeline", "task-1", path, "--json")
            self.assertEqual(0, code, stderr)
            self.assertNotIn("semantic_as_of", json.loads(stdout))
