import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint, mutation
from lifetxt.native_history import iter_item_events
from lifetxt.native_history_mutation import commit_item_mutation_with_event
from lifetxt.parser import parse_text
from lifetxt.write_operations import mutate_item_files, mutate_items


class NativeHistoryMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write("[ ] T Task id:task-1\n")

    def tearDown(self):
        self.temp.cleanup()

    def text(self):
        with open(self.path, encoding="utf-8", newline="") as handle:
            return handle.read()

    def test_status_and_event_are_one_exact_revision_write(self):
        before = self.text()
        result = commit_item_mutation_with_event(
            self.path,
            "task-1",
            "status_changed",
            "[/] T Task id:task-1\n",
            mutation.hash_text(before),
            at="2026-09-10T10:00:00Z",
            source="test",
        )
        items, diagnostics = parse_text(self.text())
        self.assertFalse([row for row in diagnostics if row.severity == "error"])
        self.assertEqual("[/]", items[0].status)
        event = iter_item_events(items)[0]
        self.assertEqual(["[ ]"], event.details["before_status"])
        self.assertEqual(["[/]"], event.details["after_status"])
        self.assertEqual([mutation.hash_text(before)], event.details["source_revision"])
        self.assertEqual(result.mutation.after_hash, mutation.hash_text(self.text()))

    def test_relation_and_schedule_payloads_must_match_actual_mutation(self):
        before = self.text()
        with self.assertRaises(ValueError):
            commit_item_mutation_with_event(
                self.path,
                "task-1",
                "relation_added",
                before,
                mutation.hash_text(before),
                field="follows",
                target="task-2",
            )
        self.assertEqual(before, self.text())

        changed = "[ ] T Task id:task-1 due:2026-09-11\n"
        result = commit_item_mutation_with_event(
            self.path,
            "task-1",
            "schedule_changed",
            changed,
            mutation.hash_text(before),
            field="due",
            at="2026-09-10T10:00:00Z",
        )
        self.assertEqual(["true"], result.event.details["before_missing"])
        self.assertEqual(["2026-09-11"], result.event.details["after"])

    def test_creation_relation_and_cancellation_routes_are_typed(self):
        created_path = os.path.join(self.temp.name, "created.txt")
        created = commit_item_mutation_with_event(
            created_path,
            "new-1",
            "created",
            "[ ] T New id:new-1\n",
            mutation.MISSING_HASH,
            at="2026-09-10T10:00:00Z",
        )
        self.assertEqual(["created"], created.event.details["event"])

        before = self.text()
        related = commit_item_mutation_with_event(
            self.path,
            "task-1",
            "relation_added",
            "[ ] T Task id:task-1 follows:task-2\n",
            mutation.hash_text(before),
            field="follows",
            target="task-2",
            at="2026-09-10T10:01:00Z",
        )
        self.assertEqual(["follows"], related.event.details["relation"])

        current = self.text()
        canceled = commit_item_mutation_with_event(
            self.path,
            "task-1",
            "canceled",
            "[-] T Task id:task-1 follows:task-2\n",
            mutation.hash_text(current),
            at="2026-09-10T10:02:00Z",
        )
        self.assertEqual(["[-]"], canceled.event.details["after_status"])

    def test_stale_revision_writes_neither_state_nor_event(self):
        before = self.text()
        with self.assertRaises(mutation.MutationConflict):
            commit_item_mutation_with_event(
                self.path,
                "task-1",
                "completed",
                "[x] T Task id:task-1\n",
                "0" * 64,
            )
        self.assertEqual(before, self.text())


class NativeHistoryCliCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        self.config = os.path.join(self.temp.name, "config.json")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write("[ ] T Task id:task-1\n")
        with open(self.config, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "paths": [self.path],
                    "write_file": self.path,
                    "ids": {"auto": True, "key": "id"},
                    "defaults": {"timezone": "UTC"},
                },
                handle,
            )

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", self.config] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def items(self):
        with open(self.path, encoding="utf-8") as handle:
            return parse_text(handle.read())[0]

    def test_done_due_and_reopen_append_typed_events(self):
        code, _out, err = self.run_cli("due", self.path, "task-1", "2026-09-12")
        self.assertEqual(0, code, err)
        code, _out, err = self.run_cli("done", self.path, "task-1")
        self.assertEqual(0, code, err)
        code, _out, err = self.run_cli("reopen", self.path, "task-1")
        self.assertEqual(0, code, err)
        self.assertEqual(
            ["schedule_changed", "completed", "reopened"],
            [row.details["event"][0] for row in iter_item_events(self.items())],
        )

    def test_dry_run_does_not_append_event(self):
        code, _out, err = self.run_cli("done", self.path, "task-1", "--dry-run")
        self.assertEqual(0, code, err)
        self.assertEqual([], iter_item_events(self.items()))

    def test_quick_with_auto_id_appends_creation_event(self):
        code, _out, err = self.run_cli("quick", "New task", "--append", self.path)
        self.assertEqual(0, code, err)
        events = iter_item_events(self.items())
        self.assertEqual(1, len(events))
        self.assertEqual(["created"], events[0].details["event"])
        self.assertEqual(["cli.quick"], events[0].details["source"])


class InferItemEventSpecsTests(unittest.TestCase):
    """#767: pure classifier a future Web UI/local TUI/Remote TUI write-path
    integration can reuse to close the cross-surface Native History parity
    gap this investigation found (see the #767 traceability entry). No
    write path calls this yet; it duplicates no logic from
    ``augment_item_mutation_with_event``/``build_item_event``, which remain
    the sole event-shape authority.
    """

    def _item(self, status, **details):
        text_details = "".join(
            " %s:%s" % (key, value) for key, value in details.items()
        )
        text = "%s T Task%s\n" % (status, text_details)
        return parse_text(text)[0][0]

    def test_no_change_infers_nothing(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]")
        after = self._item("[ ]")
        self.assertEqual([], infer_item_event_specs(before, after))

    def test_completion_is_classified_completed(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]")
        after = self._item("[x]")
        self.assertEqual(
            [{"event_type": "completed"}], infer_item_event_specs(before, after)
        )

    def test_undo_from_done_is_classified_reopened(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[x]")
        after = self._item("[ ]")
        self.assertEqual(
            [{"event_type": "reopened"}], infer_item_event_specs(before, after)
        )

    def test_cancellation_is_classified_canceled(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]")
        after = self._item("[-]")
        self.assertEqual(
            [{"event_type": "canceled"}], infer_item_event_specs(before, after)
        )

    def test_other_status_transition_is_classified_status_changed(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]")
        after = self._item("[/]")
        self.assertEqual(
            [{"event_type": "status_changed"}], infer_item_event_specs(before, after)
        )

    def test_due_change_is_classified_schedule_changed(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]", due="2026-09-20")
        after = self._item("[ ]", due="2026-09-25")
        self.assertEqual(
            [{"event_type": "schedule_changed", "field": "due"}],
            infer_item_event_specs(before, after),
        )

    def test_relation_add_and_remove_are_classified_independently(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]", follows="task-0")
        after = self._item("[ ]", realizes="plan-1")
        specs = infer_item_event_specs(before, after)
        self.assertIn(
            {"event_type": "relation_added", "field": "realizes", "target": "plan-1"},
            specs,
        )
        self.assertIn(
            {
                "event_type": "relation_removed",
                "field": "follows",
                "target": "task-0",
            },
            specs,
        )

    def test_on_from_to_at_changes_are_never_classified(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]", on="2026-09-20")
        after = self._item("[ ]", on="2026-09-25")
        self.assertEqual([], infer_item_event_specs(before, after))

    def test_multiple_simultaneous_changes_produce_multiple_specs(self):
        from lifetxt.native_history_mutation import infer_item_event_specs

        before = self._item("[ ]", due="2026-09-20")
        after = self._item("[x]", due="2026-09-25")
        specs = infer_item_event_specs(before, after)
        self.assertEqual(2, len(specs))
        self.assertIn({"event_type": "completed"}, specs)
        self.assertIn({"event_type": "schedule_changed", "field": "due"}, specs)


class SharedMutationNativeHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def path(self, name="life.txt"):
        return os.path.join(self.temp.name, name)

    def write(self, path, text):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)

    def read_items(self, path):
        with open(path, encoding="utf-8", newline="") as handle:
            return parse_text(handle.read())[0]

    def test_mutate_items_captures_supported_changes(self):
        path = self.path()
        self.write(path, "[ ] T Task id:task-1 due:2026-09-20\n")
        result = mutate_items(
            path,
            [{"id": "task-1", "status": "[x]", "set_details": {"due": ["2026-09-25"]}}],
        )
        self.assertTrue(result.changed)
        events = iter_item_events(self.read_items(path))
        self.assertEqual(
            ["completed", "schedule_changed"],
            [event.details["event"][0] for event in events],
        )

    def test_mutate_items_noop_does_not_capture_history(self):
        path = self.path()
        self.write(path, "[ ] T Task id:task-1\n")
        mutate_items(path, [{"id": "task-1", "status": "[ ]"}])
        self.assertEqual([], iter_item_events(self.read_items(path)))

    def test_mutate_item_files_captures_each_file_inside_journal_plan(self):
        first, second = self.path("one.txt"), self.path("two.txt")
        self.write(first, "[ ] T One id:one\n")
        self.write(second, "[ ] T Two id:two\n")
        mutate_item_files(
            {
                first: {"changes": [{"id": "one", "status": "[x]"}]},
                second: {"changes": [{"id": "two", "status": "[-]"}]},
            }
        )
        self.assertEqual(
            ["completed"],
            [event.details["event"][0] for event in iter_item_events(self.read_items(first))],
        )
        self.assertEqual(
            ["canceled"],
            [event.details["event"][0] for event in iter_item_events(self.read_items(second))],
        )
