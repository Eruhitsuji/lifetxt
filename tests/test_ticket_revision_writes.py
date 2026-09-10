import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import cli, surface_runtime, tickets
from lifetxt.mutation import MutationConflict
from lifetxt.native_history import item_event_diagnostics, iter_item_events
from lifetxt.native_timeline import native_timeline
from lifetxt.parser import parse_text
from lifetxt.safe_ops import ExpectedRevisionRequired
from lifetxt.ticket_revision_writes import (
    apply_ticket_relation,
    ticket_file_revision,
    ticket_write_revision_required,
)


SAMPLE = """#! timezone: UTC
# ticket section
[ ] T Login_race record:ticket id:BUG-1 tracker:bug ticket_status:new priority:high project:web
[ ] T Dependency record:ticket id:BUG-2 tracker:task ticket_status:new priority:normal project:web
"""


class TicketRevisionWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        self.config_path = os.path.join(self.temp.name, "config.json")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(SAMPLE)
        self._write_config({"paths": [self.path], "write_file": self.path})

    def tearDown(self):
        self.temp.cleanup()

    def _write_config(self, data):
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)

    def _text(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _ticket(self, ticket_id="BUG-1"):
        items, _diagnostics = parse_text(self._text())
        for item in items:
            if ticket_id in item.details.get("id", []):
                return item
        self.fail("ticket not found: %s" % ticket_id)

    def _events(self, ticket_id="BUG-1"):
        items, _diagnostics = parse_text(self._text())
        return iter_item_events(items, parent_id=ticket_id)

    def _cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.main(["--config", self.config_path] + list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_patch_accepts_current_revision_and_returns_new_revision(self):
        before = ticket_file_revision(self.path)
        item = tickets.apply_ticket_patch(
            self.path,
            "BUG-1",
            {"priority": "urgent"},
            expected_revision=before,
            require_revision=True,
        )
        self.assertEqual(before, item.revision_before)
        self.assertNotEqual(before, item.revision_after)
        self.assertTrue(item.revision_changed)
        self.assertFalse(item.revision_dry_run)
        self.assertEqual("urgent", self._ticket().details["priority"][0])
        self.assertEqual(item.revision_after, ticket_file_revision(self.path))
        self.assertIn("# ticket section\n", self._text())

    def test_stale_revision_rejects_without_overwriting_current_bytes(self):
        stale = ticket_file_revision(self.path)
        tickets.apply_ticket_patch(self.path, "BUG-1", {"assignee": "alice"})
        current_text = self._text()
        with self.assertRaises(MutationConflict):
            tickets.apply_ticket_patch(
                self.path,
                "BUG-1",
                {"priority": "low"},
                expected_revision=stale,
                require_revision=True,
            )
        self.assertEqual(current_text, self._text())
        self.assertEqual("high", self._ticket().details["priority"][0])
        self.assertEqual("alice", self._ticket().details["assignee"][0])

    def test_required_revision_refuses_missing_token(self):
        before = self._text()
        with self.assertRaises(ExpectedRevisionRequired):
            tickets.apply_ticket_patch(
                self.path,
                "BUG-1",
                {"priority": "urgent"},
                require_revision=True,
            )
        self.assertEqual(before, self._text())

    def test_dry_run_checks_revision_and_predicts_hash_without_write(self):
        revision = ticket_file_revision(self.path)
        before = self._text()
        item = tickets.apply_ticket_patch(
            self.path,
            "BUG-1",
            {"priority": "urgent"},
            expected_revision='"%s"' % revision,
            require_revision=True,
            dry_run=True,
        )
        self.assertEqual(before, self._text())
        self.assertEqual(revision, item.revision_before)
        self.assertNotEqual(revision, item.revision_after)
        self.assertTrue(item.revision_dry_run)

    def test_relation_updates_re_read_values_inside_cas_transform(self):
        revision = ticket_file_revision(self.path)
        linked = apply_ticket_relation(
            self.path,
            "BUG-1",
            "depends_on",
            "BUG-2",
            expected_revision=revision,
            require_revision=True,
        )
        self.assertEqual(["BUG-2"], self._ticket().details["depends_on"])
        current_text = self._text()
        with self.assertRaises(MutationConflict):
            apply_ticket_relation(
                self.path,
                "BUG-1",
                "related",
                "BUG-2",
                expected_revision=revision,
                require_revision=True,
            )
        self.assertEqual(current_text, self._text())
        self.assertEqual(linked.revision_after, ticket_file_revision(self.path))

    def test_duplicate_relation_add_is_a_noop(self):
        tickets.apply_ticket_patch(self.path, "BUG-1", {"depends_on": ["BUG-2"]})
        revision = ticket_file_revision(self.path)
        item = apply_ticket_relation(
            self.path,
            "BUG-1",
            "depends_on",
            "BUG-2",
            expected_revision=revision,
            require_revision=True,
        )
        self.assertFalse(item.revision_changed)
        self.assertEqual(revision, item.revision_after)

    def test_lifecycle_relation_add_and_remove_capture_atomic_native_events(self):
        for relation in ("follows", "realizes", "replaced_by"):
            with self.subTest(relation=relation):
                before = ticket_file_revision(self.path)
                linked = apply_ticket_relation(
                    self.path,
                    "BUG-1",
                    relation,
                    "BUG-2",
                    expected_revision=before,
                    require_revision=True,
                )
                added = self._events()[-1]
                self.assertEqual([], item_event_diagnostics(added))
                self.assertEqual(["relation_added"], added.details["event"])
                self.assertEqual([relation], added.details["relation"])
                self.assertEqual(["BUG-2"], added.details["target"])
                self.assertEqual([before], added.details["source_revision"])
                self.assertEqual(
                    linked.revision_after, ticket_file_revision(self.path)
                )

                before_remove = linked.revision_after
                unlinked = apply_ticket_relation(
                    self.path,
                    "BUG-1",
                    relation,
                    "BUG-2",
                    add=False,
                    expected_revision=before_remove,
                    require_revision=True,
                )
                removed = self._events()[-1]
                self.assertEqual([], item_event_diagnostics(removed))
                self.assertEqual(["relation_removed"], removed.details["event"])
                self.assertEqual([relation], removed.details["relation"])
                self.assertEqual(["BUG-2"], removed.details["target"])
                self.assertEqual(
                    [before_remove], removed.details["source_revision"]
                )
                self.assertEqual(
                    unlinked.revision_after, ticket_file_revision(self.path)
                )

    def test_lifecycle_relation_noop_and_stale_write_leave_no_orphan_event(self):
        first = apply_ticket_relation(
            self.path, "BUG-1", "follows", "BUG-2"
        )
        after_first = self._text()
        event_count = len(self._events())
        duplicate = apply_ticket_relation(
            self.path,
            "BUG-1",
            "follows",
            "BUG-2",
            expected_revision=first.revision_after,
        )
        self.assertFalse(duplicate.revision_changed)
        self.assertEqual(after_first, self._text())
        self.assertEqual(event_count, len(self._events()))

        with self.assertRaises(ValueError):
            apply_ticket_relation(
                self.path, "BUG-1", "realizes", "BUG-2", add=False
            )
        with self.assertRaisesRegex(ValueError, "Unknown ticket relation"):
            apply_ticket_relation(
                self.path, "BUG-1", "invented", "BUG-2"
            )
        self.assertEqual(after_first, self._text())
        self.assertEqual(event_count, len(self._events()))

        with self.assertRaises(MutationConflict):
            apply_ticket_relation(
                self.path,
                "BUG-1",
                "realizes",
                "BUG-2",
                expected_revision="0" * 64,
            )
        self.assertEqual(after_first, self._text())
        self.assertEqual(event_count, len(self._events()))

    def test_lifecycle_relation_event_is_visible_in_native_timeline(self):
        apply_ticket_relation(self.path, "BUG-1", "replaced_by", "BUG-2")
        items, _diagnostics = parse_text(self._text())
        result = native_timeline(items, "BUG-1", event="relation_added")
        self.assertEqual(1, len(result["events"]))
        self.assertEqual(
            "replaced_by", result["events"][0]["payload"]["relation"][0]
        )

    def test_cli_lifecycle_relation_route_captures_native_event(self):
        code, _stdout, stderr = self._cli(
            ["ticket", "link", "BUG-1", "follows", "BUG-2"]
        )
        self.assertEqual(0, code, stderr)
        self.assertEqual(["relation_added"], self._events()[0].details["event"])

    def test_cli_revision_and_stale_edit_contract(self):
        code, stdout, stderr = self._cli(["ticket", "revision", "BUG-1", "--json"])
        self.assertEqual(0, code, stderr)
        revision = json.loads(stdout)["revision"]
        code, stdout, stderr = self._cli(
            [
                "ticket",
                "edit",
                "BUG-1",
                "--set",
                "priority=urgent",
                "--revision",
                revision,
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("revision:", stdout)
        current_text = self._text()
        code, _stdout, stderr = self._cli(
            [
                "ticket",
                "assign",
                "BUG-1",
                "bob",
                "--revision",
                revision,
            ]
        )
        self.assertEqual(1, code)
        self.assertIn("conflict", stderr.lower())
        self.assertEqual(current_text, self._text())

    def test_config_can_require_revision_for_cli_writes(self):
        self._write_config(
            {
                "paths": [self.path],
                "write_file": self.path,
                "ticketing": {"write": {"require_revision": True}},
            }
        )
        self.assertTrue(
            ticket_write_revision_required(
                {"ticketing": {"write": {"require_revision": True}}}
            )
        )
        before = self._text()
        code, _stdout, stderr = self._cli(
            ["ticket", "edit", "BUG-1", "--set", "priority=urgent"]
        )
        self.assertEqual(1, code)
        self.assertIn("requires --revision", stderr)
        self.assertEqual(before, self._text())

    def test_parser_exposes_revision_options_on_every_ticket_write(self):
        parser = cli.build_parser()
        cases = {
            "edit": ["BUG-1", "--set", "priority=high"],
            "assign": ["BUG-1", "alice"],
            "close": ["BUG-1"],
            "reopen": ["BUG-1"],
            "link": ["BUG-1", "depends_on", "BUG-2"],
            "unlink": ["BUG-1", "depends_on", "BUG-2"],
        }
        for command, tail in cases.items():
            args = parser.parse_args(
                ["ticket", command]
                + tail
                + ["--revision", "abc", "--require-revision", "--dry-run"]
            )
            self.assertEqual("abc", args.expected_revision, command)
            self.assertTrue(args.require_revision, command)
            self.assertTrue(args.dry_run, command)

    def test_capabilities_publish_ticket_revision_contract(self):
        data = surface_runtime.capability_document_for(
            "cli",
            config={"ticketing": {"write": {"require_revision": True}}},
        )
        contract = data["ticket_write_revision"]
        self.assertTrue(contract["required_by_config"])
        self.assertEqual("sha256", contract["algorithm"])
        self.assertIn("edit", contract["write_operations"])
        self.assertFalse(contract["remote_writes_enabled"])


if __name__ == "__main__":
    unittest.main()
