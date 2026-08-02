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
        self.config = {"inbox": {"proposals_file": self.store}}

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
            lines = [l for l in handle.read().splitlines() if l.strip()]
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


if __name__ == "__main__":
    unittest.main()
