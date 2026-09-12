import unittest

from lifetxt.native_history import build_item_event
from lifetxt.native_semantic_as_of import semantic_as_of
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line


REVISION = "a" * 64


def _events(rows):
    return "".join(item_to_line(row) + "\n" for row in rows)


def _fixture(extra_events=()):
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
    text = (
        "[x] T Task id:task-1 due:2026-09-20\n"
        + item_to_line(created)
        + "\n"
        + _events(extra_events)
    )
    return parse_text(text)[0]


class SemanticAsOfStatusTests(unittest.TestCase):
    def test_status_known_at_creation_before_any_change(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T10:30:00Z")
        self.assertEqual("semantic-as-of-v1", result["schema"])
        self.assertEqual("task-1", result["target_id"])
        self.assertFalse(result["git_composed"])
        status = result["fields"]["status"]
        self.assertEqual("known", status["state"])
        self.assertEqual("[ ]", status["value"])
        self.assertEqual("IE-task-1-000001", status["as_of_event"])
        self.assertIsNone(status["reason"])

    def test_status_reflects_the_latest_change_before_cutoff(self):
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
        items = _fixture(extra_events=[completed])
        before = semantic_as_of(items, "task-1", "2026-09-10T11:00:00Z")
        self.assertEqual("[ ]", before["fields"]["status"]["value"])
        after = semantic_as_of(items, "task-1", "2026-09-10T13:00:00Z")
        self.assertEqual("known", after["fields"]["status"]["state"])
        self.assertEqual("[x]", after["fields"]["status"]["value"])
        self.assertEqual("IE-task-1-000002", after["fields"]["status"]["as_of_event"])

    def test_status_unavailable_before_the_creation_event(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T09:00:00Z")
        status = result["fields"]["status"]
        self.assertEqual("unavailable", status["state"])
        self.assertIsNone(status["value"])
        self.assertEqual("no_status_capture_before_cutoff", status["reason"])

    def test_status_partial_when_item_history_is_not_complete_from_creation(self):
        # A status_changed event with no preceding "created" event leaves
        # native_history_completeness().item incomplete, so even a real
        # match must be reported partial rather than known.
        status_changed = build_item_event(
            "task-2",
            "status_changed",
            "2026-09-10T10:00:00Z",
            1,
            "ITX-9",
            REVISION,
            before_status="[ ]",
            after_status="[/]",
        )
        text = "[/] T Other id:task-2\n" + item_to_line(status_changed) + "\n"
        items = parse_text(text)[0]
        result = semantic_as_of(items, "task-2", "2026-09-10T11:00:00Z")
        status = result["fields"]["status"]
        self.assertEqual("partial", status["state"])
        self.assertEqual("[/]", status["value"])


class SemanticAsOfDueTests(unittest.TestCase):
    def test_due_unavailable_when_never_captured(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T11:00:00Z")
        due = result["fields"]["due"]
        self.assertEqual("unavailable", due["state"])
        self.assertEqual("no_schedule_changed_capture", due["reason"])

    def test_due_known_after_a_captured_change(self):
        schedule_changed = build_item_event(
            "task-1",
            "schedule_changed",
            "2026-09-11T09:00:00Z",
            2,
            "ITX-3",
            REVISION,
            field="due",
            before="2026-09-20",
            after="2026-09-25",
        )
        items = _fixture(extra_events=[schedule_changed])
        before = semantic_as_of(items, "task-1", "2026-09-10T23:00:00Z")
        self.assertEqual(
            "no_schedule_changed_capture_before_cutoff",
            before["fields"]["due"]["reason"],
        )
        after = semantic_as_of(items, "task-1", "2026-09-12T00:00:00Z")
        due = after["fields"]["due"]
        self.assertEqual("known", due["state"])
        self.assertEqual("2026-09-25", due["value"])
        self.assertEqual("IE-task-1-000002", due["as_of_event"])

    def test_due_reports_a_cleared_value_as_none(self):
        cleared = build_item_event(
            "task-1",
            "schedule_changed",
            "2026-09-11T09:00:00Z",
            2,
            "ITX-4",
            REVISION,
            field="due",
            before="2026-09-20",
            after_missing="true",
        )
        items = _fixture(extra_events=[cleared])
        result = semantic_as_of(items, "task-1", "2026-09-12T00:00:00Z")
        due = result["fields"]["due"]
        self.assertEqual("known", due["state"])
        self.assertIsNone(due["value"])


class SemanticAsOfRelationTests(unittest.TestCase):
    def test_relation_unavailable_with_no_relation_events_at_all(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T11:00:00Z")
        for relation in ("follows", "realizes", "replaced_by"):
            self.assertEqual("unavailable", result["fields"][relation]["state"])
            self.assertEqual("no_relation_capture", result["fields"][relation]["reason"])

    def test_relation_replays_add_and_remove_up_to_cutoff(self):
        added = build_item_event(
            "task-1",
            "relation_added",
            "2026-09-11T09:00:00Z",
            2,
            "ITX-5",
            REVISION,
            relation="follows",
            target="task-0",
        )
        removed = build_item_event(
            "task-1",
            "relation_removed",
            "2026-09-12T09:00:00Z",
            3,
            "ITX-6",
            REVISION,
            relation="follows",
            target="task-0",
        )
        items = _fixture(extra_events=[added, removed])
        mid = semantic_as_of(items, "task-1", "2026-09-11T12:00:00Z")
        follows_mid = mid["fields"]["follows"]
        self.assertEqual("known", follows_mid["state"])
        self.assertEqual(["task-0"], follows_mid["values"])
        after = semantic_as_of(items, "task-1", "2026-09-13T00:00:00Z")
        self.assertEqual([], after["fields"]["follows"]["values"])

    def test_relation_known_empty_when_captured_but_never_added_before_cutoff(self):
        added_later = build_item_event(
            "task-1",
            "relation_added",
            "2026-09-15T09:00:00Z",
            2,
            "ITX-7",
            REVISION,
            relation="realizes",
            target="plan-1",
        )
        items = _fixture(extra_events=[added_later])
        result = semantic_as_of(items, "task-1", "2026-09-11T00:00:00Z")
        realizes = result["fields"]["realizes"]
        self.assertEqual("known", realizes["state"])
        self.assertEqual([], realizes["values"])


class SemanticAsOfNotReconstructableTests(unittest.TestCase):
    def test_on_from_to_at_always_unavailable(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T11:00:00Z")
        for field in ("on", "from", "to", "at"):
            self.assertEqual("unavailable", result["fields"][field]["state"])
            self.assertEqual(
                "no_schedule_changed_capture", result["fields"][field]["reason"]
            )


class SemanticAsOfCutoffTests(unittest.TestCase):
    def test_accepts_a_raw_string_cutoff_via_the_shared_parser(self):
        result = semantic_as_of(_fixture(), "task-1", "2026-09-10T10:30:00Z")
        self.assertEqual("2026-09-10T10:30:00Z", result["as_of"])

    def test_rejects_a_naive_datetime_cutoff(self):
        import datetime

        with self.assertRaises(ValueError):
            semantic_as_of(
                _fixture(), "task-1", datetime.datetime(2026, 9, 10, 10, 30)
            )

    def test_unknown_target_raises(self):
        with self.assertRaises(ValueError):
            semantic_as_of(_fixture(), "nope", "2026-09-10T10:30:00Z")


if __name__ == "__main__":
    unittest.main()
