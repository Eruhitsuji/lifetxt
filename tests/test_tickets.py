import os
import tempfile
import unittest

from lifetxt.parser import parse_text
from lifetxt import tickets


CONFIG = {
    "ticketing": {
        "id_prefix": "BUG",
        "trackers": ["bug", "feature", "task"],
        "priorities": ["low", "normal", "high"],
        "severities": ["minor", "major", "critical"],
        "required_fields": ["assignee"],
    }
}

SAMPLE = """#! timezone: UTC
[ ] T Login_fails record:ticket id:BUG-1 tracker:bug ticket_status:new priority:high assignee:alice project:web
[/] T Dark_mode record:ticket id:BUG-2 tracker:feature ticket_status:in_progress priority:normal assignee:bob
[x] T Bad_status record:ticket id:BUG-3 tracker:bug ticket_status:new priority:low reporter:carol
[ ] T Bad_registry record:ticket id:BUG-4 tracker:widget ticket_status:new priority:mega assignee:x
[ ] T Plain project:web
"""


class TicketModelTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_is_ticket_only_marked_records(self):
        marked = [t for t in self.items if tickets.is_ticket(t)]
        self.assertEqual(4, len(marked))

    def test_next_ticket_id(self):
        self.assertEqual("BUG-5", tickets.next_ticket_id(self.items, CONFIG))

    def test_ticket_list_and_filters(self):
        rows = tickets.ticket_list(self.items, CONFIG)
        self.assertEqual(4, len(rows))
        open_rows = tickets.ticket_list(self.items, CONFIG, {"open_only": True})
        # BUG-3 is [x] (closed-ish), so excluded.
        self.assertNotIn("BUG-3", [r["id"] for r in open_rows])
        bugs = tickets.ticket_list(self.items, CONFIG, {"tracker": "bug"})
        self.assertEqual({"BUG-1", "BUG-3"}, {r["id"] for r in bugs})

    def test_status_map_override(self):
        config = {"ticketing": {"statuses": {"custom": {"life_status": "[/]"}}}}
        self.assertEqual("[/]", tickets.status_map(config)["custom"])

    def test_validate_status_mismatch(self):
        codes = {d["code"] for d in tickets.validate_ticket(self.items[2], CONFIG)}
        self.assertIn("TK003", codes)  # ticket_status new but [x]

    def test_validate_registry_and_required(self):
        codes = {d["code"] for d in tickets.validate_ticket(self.items[3], CONFIG)}
        self.assertIn("TK004", codes)  # unknown tracker/priority

    def test_validate_missing_required(self):
        codes = {d["code"] for d in tickets.validate_ticket(self.items[1], CONFIG)}
        self.assertNotIn("TK005", codes)  # BUG-2 has assignee
        codes = {d["code"] for d in tickets.validate_ticket(self.items[2], CONFIG)}
        self.assertIn("TK005", codes)  # BUG-3 missing assignee

    def test_ticket_view_relations_and_backlinks(self):
        view = tickets.ticket_view(self.items[0], CONFIG, self.items, key="id")
        self.assertEqual("BUG-1", view["summary"]["id"])
        self.assertEqual("bug", view["fields"]["tracker"])

    def test_build_ticket_line_applies_defaults(self):
        line = tickets.build_ticket_line(CONFIG, "New crash", ticket_id="BUG-9")
        items, diags = parse_text("#! timezone: UTC\n%s\n" % line)
        self.assertFalse([d for d in diags if d.severity == "error"])
        self.assertEqual(["ticket"], items[0].details.get("record"))
        self.assertEqual(["new"], items[0].details.get("ticket_status"))


class TicketWriteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write(
                "#! timezone: UTC\n"
                "[ ] T Login record:ticket id:BUG-1 tracker:bug ticket_status:new priority:high\n"
            )

    def tearDown(self):
        self.temp.cleanup()

    def _reload(self):
        with open(self.path, "r", encoding="utf-8") as handle:
            items, _ = parse_text(handle.read())
        return items[0]

    def test_find_ticket_file(self):
        self.assertEqual(self.path, tickets.find_ticket_file([self.path], "BUG-1"))
        self.assertIsNone(tickets.find_ticket_file([self.path], "BUG-9"))

    def test_apply_patch_assign(self):
        tickets.apply_ticket_patch(self.path, "BUG-1", {"assignee": "alice"})
        self.assertEqual(["alice"], self._reload().details.get("assignee"))

    def test_apply_patch_close_changes_status(self):
        updates, life = tickets.transition_updates(CONFIG, "closed", actor="alice")
        tickets.apply_ticket_patch(self.path, "BUG-1", updates, status=life)
        item = self._reload()
        self.assertEqual("[x]", item.status)
        self.assertEqual(["closed"], item.details.get("ticket_status"))
        self.assertEqual(["alice"], item.details.get("closed_by"))

    def test_apply_patch_removes_field(self):
        tickets.apply_ticket_patch(self.path, "BUG-1", {"priority": None})
        self.assertIsNone(self._reload().details.get("priority"))

    def test_apply_patch_unknown_ticket(self):
        with self.assertRaises(ValueError):
            tickets.apply_ticket_patch(self.path, "BUG-9", {"assignee": "x"})


if __name__ == "__main__":
    unittest.main()
