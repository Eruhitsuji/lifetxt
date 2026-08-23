import os
import tempfile
import unittest
from collections import OrderedDict

from lifetxt import inbox
from lifetxt.parser import parse_text


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = os.path.join(self.temp.name, "proposals.json")
        self.target = os.path.join(self.temp.name, "life.txt")
        self.config = {
            "inbox": {"proposals_file": self.store},
            "write_file": self.target,
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_stage_and_list(self):
        inbox.stage_create(
            self.config, "Buy milk", details={"project": "home"}, source="capture"
        )
        proposals = inbox.list_proposals(self.config)
        self.assertEqual(1, len(proposals))
        self.assertEqual("pending", proposals[0]["status"])
        self.assertEqual("capture", proposals[0]["source"])

    def test_proposal_to_line_roundtrips(self):
        proposal = inbox.stage_create(
            self.config, "Call Bob", details={"assignee": "bob"}
        )
        line = inbox.proposal_to_line(proposal)
        items, diags = parse_text("#! timezone: UTC\n%s\n" % line)
        self.assertFalse([d for d in diags if d.severity == "error"])
        self.assertEqual(["bob"], items[0].details.get("assignee"))

    def test_edit_pending_proposal(self):
        proposal = inbox.stage_create(self.config, "Task")
        inbox.edit_proposal(
            self.config, proposal["id"], title="Renamed", details={"project": "web"}
        )
        updated = inbox.get_proposal(self.config, proposal["id"])
        change = updated["changes"][0]
        self.assertEqual("Renamed", change["title"])
        self.assertEqual(["web"], change["details"]["project"])

    def test_accept_appends_and_marks_accepted(self):
        proposal = inbox.stage_create(self.config, "Ship", details={"project": "web"})
        result = inbox.accept(self.config, proposal["id"], self.target)
        self.assertTrue(result["applied"])
        with open(self.target, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("Ship", content)
        self.assertEqual(
            "accepted", inbox.get_proposal(self.config, proposal["id"])["status"]
        )

    def test_accept_twice_fails(self):
        proposal = inbox.stage_create(self.config, "Once")
        inbox.accept(self.config, proposal["id"], self.target)
        with self.assertRaises(ValueError):
            inbox.accept(self.config, proposal["id"], self.target)

    def test_reject_and_defer(self):
        p1 = inbox.stage_create(self.config, "A")
        p2 = inbox.stage_create(self.config, "B")
        inbox.reject(self.config, p1["id"])
        inbox.defer(self.config, p2["id"])
        self.assertEqual(
            "rejected", inbox.get_proposal(self.config, p1["id"])["status"]
        )
        self.assertEqual(
            "deferred", inbox.get_proposal(self.config, p2["id"])["status"]
        )

    def test_batch_apply(self):
        ids = [inbox.stage_create(self.config, "T%d" % i)["id"] for i in range(3)]
        report = inbox.batch_apply(self.config, ids, self.target)
        self.assertEqual(3, report["applied"])
        self.assertEqual(3, report["total"])
        with open(self.target, "r", encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        self.assertEqual(3, len(lines))

    def test_batch_apply_reports_unknown(self):
        report = inbox.batch_apply(self.config, ["P-nope"], self.target)
        self.assertEqual(0, report["applied"])
        self.assertFalse(report["results"][0]["applied"])

    def test_filter_by_status(self):
        p1 = inbox.stage_create(self.config, "A")
        inbox.stage_create(self.config, "B")
        inbox.reject(self.config, p1["id"])
        self.assertEqual(1, len(inbox.list_proposals(self.config, status="rejected")))
        self.assertEqual(1, len(inbox.list_proposals(self.config, status="pending")))

    def test_summary_counts(self):
        p1 = inbox.stage_create(self.config, "A")
        inbox.stage_create(self.config, "B")
        inbox.accept(self.config, p1["id"], self.target)
        summary = inbox.inbox_summary(self.config)
        self.assertEqual(2, summary["total"])
        self.assertEqual(1, summary["counts"]["accepted"])
        self.assertEqual(1, summary["counts"]["pending"])

    def test_edit_non_pending_fails(self):
        proposal = inbox.stage_create(self.config, "A")
        inbox.reject(self.config, proposal["id"])
        with self.assertRaises(ValueError):
            inbox.edit_proposal(self.config, proposal["id"], title="X")

    def test_missing_store_is_empty(self):
        self.assertEqual([], inbox.list_proposals(self.config))

    def test_stage_create_captures_target_and_revision(self):
        with open(self.target, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: UTC\n[ ] T Existing\n")

        proposal = inbox.stage_create(self.config, "New")

        self.assertEqual(self.target, proposal["staged_target"])
        self.assertTrue(proposal["expected_revision"])

    def test_stage_create_populates_provenance(self):
        proposal = inbox.stage_create(self.config, "New", source="mcp")
        self.assertEqual("mcp", proposal["provenance"]["source"])

    def test_accept_succeeds_when_target_unchanged_since_staging(self):
        proposal = inbox.stage_create(self.config, "Ship")
        result = inbox.accept(self.config, proposal["id"], self.target)
        self.assertTrue(result["applied"])

    def test_accept_refuses_when_target_changed_since_staging(self):
        proposal = inbox.stage_create(self.config, "Ship")
        with open(self.target, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Interloper\n")

        with self.assertRaises(ValueError) as caught:
            inbox.accept(self.config, proposal["id"], self.target)

        self.assertIn("stale", str(caught.exception).lower())
        with open(self.target, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("Ship", content)
        self.assertEqual(
            "pending", inbox.get_proposal(self.config, proposal["id"])["status"]
        )

    def test_accept_with_explicit_revision_overrides_the_staged_one(self):
        proposal = inbox.stage_create(self.config, "Ship")
        with open(self.target, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Interloper\n")

        # An explicit caller-supplied revision takes precedence over the
        # proposal's own stale stored one; using the file's real current
        # hash here proves the override, not the stored value, is honored.
        from lifetxt.write_operations import snapshot

        current = snapshot(self.target).content_hash
        result = inbox.accept(
            self.config, proposal["id"], self.target, expected_revision=current
        )
        self.assertTrue(result["applied"])

    def test_accept_into_a_different_target_skips_the_staleness_check(self):
        other = os.path.join(self.temp.name, "other.txt")
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("#! timezone: UTC\n[ ] T Unrelated\n")
        proposal = inbox.stage_create(self.config, "Ship")

        result = inbox.accept(self.config, proposal["id"], other)

        self.assertTrue(result["applied"])

    def test_batch_apply_of_proposals_staged_before_any_were_applied_succeeds(self):
        # All three are staged against the same not-yet-existing target
        # before any of them is applied; only the first is checked against
        # its own stage-time snapshot, so the batch must still fully apply.
        ids = [inbox.stage_create(self.config, "T%d" % i)["id"] for i in range(3)]

        report = inbox.batch_apply(self.config, ids, self.target)

        self.assertEqual(3, report["applied"])
        self.assertEqual(3, report["total"])

    def test_batch_apply_reports_a_stale_first_proposal_without_crashing(self):
        proposal = inbox.stage_create(self.config, "Ship")
        with open(self.target, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Interloper\n")

        report = inbox.batch_apply(self.config, [proposal["id"]], self.target)

        self.assertEqual(0, report["applied"])
        self.assertIn("stale", report["results"][0]["error"].lower())

    def test_accepting_a_ticket_shaped_proposal_writes_a_creation_event(self):
        proposal = inbox.stage_create(
            self.config,
            "Fix the bug",
            kind="T",
            details={
                "record": "ticket",
                "id": "TK-1",
                "project": "web",
                "tracker": "bug",
            },
            source="mcp",
        )

        result = inbox.accept(self.config, proposal["id"], self.target)

        self.assertIn("event_line", result)
        self.assertIn("record:ticket_event", result["event_line"])
        self.assertIn("event:created", result["event_line"])
        with open(self.target, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("record:ticket_event", content)
        self.assertIn("parent:TK-1", content)

    def test_accepting_a_non_ticket_proposal_never_adds_an_event(self):
        proposal = inbox.stage_create(self.config, "Buy milk")

        result = inbox.accept(self.config, proposal["id"], self.target)

        self.assertNotIn("event_line", result)
        with open(self.target, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertNotIn("record:ticket_event", content)

    def test_ticket_shaped_proposal_without_an_id_is_treated_as_non_ticket(self):
        # A ticket contract requires id:, and staging does not auto-generate
        # one the way `ticket new` does; without it there is nothing
        # meaningful for a creation event to reference.
        proposal = inbox.stage_create(
            self.config, "Fix", kind="T", details={"record": "ticket"}
        )

        result = inbox.accept(self.config, proposal["id"], self.target)

        self.assertNotIn("event_line", result)


class InboxIdempotencyTests(unittest.TestCase):
    """stage_create()'s optional idempotency_key (#512/#514).

    Without a key, this project's existing behavior is unchanged: retrying
    stage_create() with identical arguments still creates a second, distinct
    proposal (this is the exact duplicate-staging gap #512 found, and is
    preserved here as a locked-in baseline rather than silently fixed by
    making the key mandatory).
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = os.path.join(self.temp.name, "proposals.json")
        self.target = os.path.join(self.temp.name, "life.txt")
        self.config = {
            "inbox": {"proposals_file": self.store},
            "write_file": self.target,
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_omitting_the_key_preserves_todays_duplicate_staging_behavior(self):
        inbox.stage_create(self.config, "Buy milk", details={"project": "home"})
        inbox.stage_create(self.config, "Buy milk", details={"project": "home"})

        proposals = inbox.list_proposals(self.config)
        self.assertEqual(2, len(proposals))
        self.assertNotEqual(proposals[0]["id"], proposals[1]["id"])

    def test_repeating_the_same_key_and_content_does_not_duplicate(self):
        first = inbox.stage_create(
            self.config,
            "Buy milk",
            details={"project": "home"},
            idempotency_key="retry-1",
        )
        second = inbox.stage_create(
            self.config,
            "Buy milk",
            details={"project": "home"},
            idempotency_key="retry-1",
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, len(inbox.list_proposals(self.config)))

    def test_repeating_the_key_with_different_content_fails_loudly(self):
        inbox.stage_create(self.config, "Buy milk", idempotency_key="retry-1")

        with self.assertRaises(ValueError) as caught:
            inbox.stage_create(self.config, "Buy bread", idempotency_key="retry-1")

        self.assertIn("retry-1", str(caught.exception))
        self.assertEqual(1, len(inbox.list_proposals(self.config)))

    def test_key_is_persisted_on_the_proposal_record(self):
        proposal = inbox.stage_create(
            self.config, "Buy milk", idempotency_key="retry-1"
        )
        self.assertEqual("retry-1", proposal["idempotency_key"])

        no_key = inbox.stage_create(self.config, "Buy bread")
        self.assertEqual("", no_key["idempotency_key"])

    def test_reusing_a_key_after_the_original_was_accepted_returns_it_unchanged(self):
        first = inbox.stage_create(self.config, "Buy milk", idempotency_key="retry-1")
        inbox.accept(self.config, first["id"], self.target)

        second = inbox.stage_create(self.config, "Buy milk", idempotency_key="retry-1")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual("accepted", second["status"])
        self.assertEqual(1, len(inbox.list_proposals(self.config)))

    def test_mcp_stage_proposal_tool_forwards_the_key(self):
        from lifetxt.mcp import McpContext, call_tool

        context = McpContext(
            paths=[self.target],
            writable_path=self.target,
            config=self.config,
            read_only=False,
        )
        first = call_tool(
            "stage_proposal",
            {"title": "Buy milk", "idempotency_key": "retry-1"},
            context,
        )
        second = call_tool(
            "stage_proposal",
            {"title": "Buy milk", "idempotency_key": "retry-1"},
            context,
        )

        self.assertEqual(first["proposal"]["id"], second["proposal"]["id"])
        self.assertEqual(1, len(inbox.list_proposals(self.config)))


if __name__ == "__main__":
    unittest.main()
