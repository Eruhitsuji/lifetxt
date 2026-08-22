"""Ticket creation now emits its own record:ticket_event (#497).

Covers lifetxt.ticket_activity.build_creation_event directly, and the two
production call sites that route through it: the CLI `ticket new` command
(both the original lifetxt/cli.py implementation and the
lifetxt/ticket_custom_fields.py monkey-patched duplicate that actually runs
during a normal `lifetxt` invocation) and Unified Inbox proposal acceptance,
covered separately in tests/test_inbox.py.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest

from lifetxt import entrypoint
from lifetxt.parser import parse_text
from lifetxt.ticket_activity import build_creation_event, validate_ticket_history


class BuildCreationEventTests(unittest.TestCase):
    def test_reuses_build_ticket_event_shape_with_created_type(self):
        event = build_creation_event(
            "TK-1", author="alice", project="web", tracker="bug"
        )

        self.assertEqual("N", event.kind)
        self.assertEqual(["ticket_event"], event.details["record"])
        self.assertEqual(["created"], event.details["event"])
        self.assertEqual(["TK-1"], event.details["parent"])
        self.assertEqual(["alice"], event.details["author"])
        self.assertEqual(["1"], event.details["sequence"])
        self.assertEqual(["new"], event.details["ticket_revision"])
        self.assertEqual(["web"], event.details["project"])
        self.assertEqual(["bug"], event.details["tracker"])

    def test_transaction_id_is_deterministically_derived_when_not_supplied(self):
        event = build_creation_event("TK-2", at="2026-08-22T10:00:00Z")
        self.assertEqual(
            ["TX-TK-2-000001-20260822-100000"], event.details["transaction"]
        )

    def test_explicit_transaction_id_is_honoured(self):
        event = build_creation_event("TK-3", transaction_id="TX-custom")
        self.assertEqual(["TX-custom"], event.details["transaction"])

    def test_author_defaults_to_local_when_not_supplied(self):
        event = build_creation_event("TK-4")
        self.assertEqual(["local"], event.details["author"])


class TicketNewCreationEventCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.config_path = os.path.join(self.temp_dir.name, "config.json")
        with open(self.life, "w", encoding="utf-8", newline="") as handle:
            handle.write("#! timezone: UTC\n")
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "paths": [self.life],
                    "write_file": self.life,
                    "user": {"name": "alice"},
                },
                handle,
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entrypoint.main(["--config", self.config_path] + list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def read_text(self):
        with open(self.life, encoding="utf-8", newline="") as handle:
            return handle.read()

    def test_ticket_new_writes_a_companion_creation_event(self):
        code, _stdout, stderr = self.run_cli(
            ["ticket", "new", "Fix the bug", "--tracker", "bug", "--project", "web"]
        )
        self.assertEqual(0, code, stderr)

        text = self.read_text()
        self.assertIn("record:ticket_event", text)
        self.assertIn("event:created", text)

        items, diagnostics = parse_text(text)
        self.assertFalse([d for d in diagnostics if d.severity == "error"], diagnostics)
        errors = validate_ticket_history(items)
        self.assertEqual([], errors, errors)

    def test_creation_event_references_the_new_ticket_by_id(self):
        code, _stdout, stderr = self.run_cli(["ticket", "new", "Fix the bug"])
        self.assertEqual(0, code, stderr)

        items, _diagnostics = parse_text(self.read_text())
        ticket = next(item for item in items if item.kind == "T")
        event = next(item for item in items if item.kind == "N")
        ticket_id = ticket.details["id"][0]
        self.assertEqual([ticket_id], event.details["parent"])

    def test_dry_run_does_not_write_a_creation_event(self):
        code, stdout, stderr = self.run_cli(
            ["ticket", "new", "Fix the bug", "--dry-run"]
        )
        self.assertEqual(0, code, stderr)
        self.assertNotIn("record:ticket_event", stdout)
        self.assertEqual("#! timezone: UTC\n", self.read_text())


if __name__ == "__main__":
    unittest.main()
