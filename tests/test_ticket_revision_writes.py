import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import cli, tickets
from lifetxt.mutation import MutationConflict
from lifetxt.parser import parse_text
from lifetxt.safe_ops import ExpectedRevisionRequired
from lifetxt import surface_runtime
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
        tickets.apply_ticket_patch(
            self.path, "BUG-1", {"depends_on": ["BUG-2"]}
        )
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

    def test_cli_revision_and_stale_edit_contract(self):
        code, stdout, stderr = self._cli(["ticket", "revision", "BUG-1", "--json"])
        self.assertEqual(0, code, stderr)
        revision = json.loads(stdout)["revision"]
        code, stdout, stderr = self._cli(
            [
                "ticket", "edit", "BUG-1",
                "--set", "priority=urgent",
                "--revision", revision,
            ]
        )
        self.assertEqual(0, code, stderr)
        self.assertIn("revision:", stdout)
        current_text = self._text()
        code, _stdout, stderr = self._cli(
            [
                "ticket", "assign", "BUG-1", "bob",
                "--revision", revision,
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
                ["ticket", command] + tail
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
