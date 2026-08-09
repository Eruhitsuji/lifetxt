import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.ids import id_audit
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line
from lifetxt.ticket_activity import build_ticket_event, build_time_entry
from lifetxt.ticket_revision_writes import ticket_file_revision
from lifetxt.ticket_workflow import apply_transition
from lifetxt.timezone_policy import timezone_context


class GeneratedRecordValidationTests(unittest.TestCase):
    def _codes(self, text):
        _items, diagnostics = parse_text(text)
        return [diagnostic.code for diagnostic in diagnostics]

    def test_project_record_owned_fields_do_not_emit_generic_custom_or_presence_warnings(self):
        codes = self._codes(
            "[N] N project_meta record:project project:demo state:active "
            "owner:self id:project_meta\n"
        )
        self.assertNotIn("W106", codes)
        self.assertNotIn("W207", codes)

    def test_ticket_record_owned_fields_do_not_emit_generic_custom_warnings(self):
        codes = self._codes(
            "[ ] T ticket record:ticket id:TK-1 tracker:task ticket_status:new "
            "priority:normal severity:minor project:demo assignee:self\n"
        )
        self.assertNotIn("W106", codes)

    def test_ticket_event_builder_owned_fields_do_not_emit_generic_custom_warnings(self):
        event = build_ticket_event(
            "TK-1",
            "transition",
            "self",
            "2026-08-09T01:00:00Z",
            1,
            "TX-TK-1-000001",
            "a" * 64,
            changes=['{"field":"ticket_status","before":["new"],"after":["in_progress"]}'],
            body="Started",
            project="demo",
            tracker="task",
            from_status="new",
            to_status="in_progress",
            provider="local",
            references=["ref-1"],
            extra={
                "role": "administrator",
                "watcher": "self",
                "activity": "development",
                "assignee": "self",
                "version": "VER-1",
                "sprint": "SPR-1",
            },
        )
        codes = self._codes(item_to_line(event) + "\n")
        self.assertNotIn("W106", codes)

    def test_time_entry_builder_owned_fields_do_not_emit_generic_custom_warnings(self):
        entry = build_time_entry(
            "TK-1",
            "demo",
            "self",
            "development",
            "2026-08-09",
            "30m",
            1,
            "EV-TK-1-000001",
            "2026-08-09T01:00:00Z",
            comment="Worked",
            source="manual",
            timer_ref="timer-1",
            corrects="TIME-TK-1-000000",
        )
        codes = self._codes(item_to_line(entry) + "\n")
        self.assertNotIn("W106", codes)

    def test_ticket_history_unknown_custom_key_still_warns(self):
        event = build_ticket_event(
            "TK-1",
            "transition",
            "self",
            "2026-08-09T01:00:00Z",
            1,
            "TX-TK-1-000001",
            "a" * 64,
        )
        event.details["custom_thing"] = ["value"]
        codes = self._codes(item_to_line(event) + "\n")
        self.assertIn("W106", codes)

    def test_generic_note_custom_key_still_warns(self):
        codes = self._codes("[N] N note id:n1 custom_thing:value\n")
        self.assertIn("W106", codes)

    def test_unknown_record_marker_does_not_gain_built_in_field_status(self):
        codes = self._codes("[N] N note id:n1 record:custom custom_thing:value\n")
        self.assertGreaterEqual(codes.count("W106"), 2)

    def test_presence_state_validation_is_unchanged(self):
        codes = self._codes(
            "[/] S presence from:2026-08-09T10:00 state:not-a-presence-state "
            "person:self\n"
        )
        self.assertIn("W207", codes)


class TicketWorkflowCompletionMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.life_path = os.path.join(self.tempdir.name, "life.txt")
        with open(self.life_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "[ ] T Workflow record:ticket id:TK-1 tracker:task "
                "ticket_status:new priority:normal project:demo assignee:self\n"
            )

    def tearDown(self):
        self.tempdir.cleanup()

    def _read(self):
        with open(self.life_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        items, diagnostics = parse_text(text)
        ticket = next(
            item
            for item in items
            if "ticket" in item.details.get("record", [])
            and item.details.get("id") == ["TK-1"]
        )
        return text, ticket, diagnostics

    def _transition(self, status, at, resolution=None):
        revision = ticket_file_revision(self.life_path)
        return apply_transition(
            self.life_path,
            "TK-1",
            status,
            "self",
            "administrator",
            revision,
            resolution=resolution,
            comment="workflow test",
            at=at,
        )

    def test_completed_transition_sets_done_preserves_it_on_close_and_reopen_clears_it(self):
        with timezone_context("Asia/Tokyo"):
            self._transition("in_progress", "2026-08-09T23:50:00+09:00")
            self._transition(
                "resolved",
                "2026-08-10T00:30:00+09:00",
                resolution="verified",
            )
            _text, ticket, diagnostics = self._read()
            self.assertEqual("[x]", ticket.status)
            self.assertEqual(["2026-08-10"], ticket.details.get("done"))
            self.assertNotIn("W103", [diagnostic.code for diagnostic in diagnostics])
            self.assertNotIn("W106", [diagnostic.code for diagnostic in diagnostics])

            self._transition("closed", "2026-08-11T10:00:00+09:00")
            _text, ticket, diagnostics = self._read()
            self.assertEqual(["2026-08-10"], ticket.details.get("done"))
            self.assertNotIn("W103", [diagnostic.code for diagnostic in diagnostics])

            self._transition("new", "2026-08-12T10:00:00+09:00")
            _text, ticket, diagnostics = self._read()
            self.assertEqual("[ ]", ticket.status)
            self.assertNotIn("done", ticket.details)
            self.assertNotIn("W104", [diagnostic.code for diagnostic in diagnostics])
            self.assertNotIn("W106", [diagnostic.code for diagnostic in diagnostics])


class CaptureContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name
        self.config_dir = os.path.join(self.root, "config")
        self.cwd = os.path.join(self.root, "cwd")
        os.makedirs(self.config_dir)
        os.makedirs(self.cwd)
        self.life_path = os.path.join(self.config_dir, "life.txt")
        with open(self.life_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Base id:base project:demo\n")
        self.config_path = os.path.join(self.config_dir, ".lifetxt.json")
        with open(self.config_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "config_version": 1,
                    "default_workspace": "personal",
                    "workspaces": {
                        "personal": {
                            "sources": [
                                {
                                    "path": "life.txt",
                                    "role": "primary",
                                    "required": True,
                                    "writable": True,
                                }
                            ],
                            "write_file": "life.txt",
                        }
                    },
                    "ids": {"auto": True, "key": "id"},
                },
                handle,
            )

    def tearDown(self):
        self.tempdir.cleanup()

    @contextlib.contextmanager
    def _unrelated_cwd(self):
        previous = os.getcwd()
        os.chdir(self.cwd)
        try:
            yield
        finally:
            os.chdir(previous)

    def _run(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = entrypoint.main(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_project_new_applies_auto_id_without_creating_generic_warnings(self):
        with self._unrelated_cwd():
            result, stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "project",
                    "new",
                    "demo-project",
                    "--owner",
                    "self",
                    "--state",
                    "active",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertNotIn("W106", stderr)
        self.assertNotIn("W207", stderr)
        self.assertIn("id:note_", stdout)

        with open(self.life_path, "r", encoding="utf-8") as handle:
            items, diagnostics = parse_text(handle.read())
        self.assertFalse([d for d in diagnostics if d.code in ("W106", "W207")])
        project_items = [
            item for item in items if "project" in item.details.get("record", [])
        ]
        self.assertEqual(len(project_items), 1)
        self.assertTrue(project_items[0].details.get("id"))
        self.assertEqual(id_audit(items)["missing_count"], 0)

    def test_quick_resolves_existing_reference_from_named_workspace(self):
        with self._unrelated_cwd():
            result, _stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "quick",
                    "Dependent",
                    "--id",
                    "dependent",
                    "--project",
                    "demo",
                    "--depends_on",
                    "base",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertNotIn("W215", stderr)

        with open(self.life_path, "r", encoding="utf-8") as handle:
            _items, diagnostics = parse_text(handle.read())
        self.assertNotIn("W215", [diagnostic.code for diagnostic in diagnostics])

    def test_quick_still_warns_for_truly_missing_reference(self):
        with self._unrelated_cwd():
            result, _stdout, stderr = self._run(
                [
                    "--config",
                    self.config_path,
                    "quick",
                    "Missing dependency",
                    "--id",
                    "missing-dependent",
                    "--depends_on",
                    "does-not-exist",
                ]
            )
        self.assertEqual(result, 0, stderr)
        self.assertIn("W215", stderr)


if __name__ == "__main__":
    unittest.main()
