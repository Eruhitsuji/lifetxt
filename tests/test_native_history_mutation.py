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
