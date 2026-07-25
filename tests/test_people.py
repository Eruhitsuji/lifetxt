import datetime
import unittest

from lifetxt.parser import parse_text
from lifetxt import people


TODAY = datetime.date(2026, 7, 24)

CONFIG = {
    "user": {"name": "self", "aliases": ["me"]},
    "teams": {"platform": {"members": ["alice", "self"]}},
    "groups": {"eng": {"members": ["alice", "bob"]}},
}

SAMPLE = """#! timezone: UTC
[N] N Website record:project project:web owner:alice
[ ] T Design project:web assignee:alice due:2026-07-01
[?] T WaitReply project:web assignee:alice
[x] T Done project:web assignee:alice
[ ] T MyTask assignee:me
[ ] M Ping sender:bob recipient:alice body:hi
[ ] M Report sender:alice recipient:self body:done
[ ] E Standup attendee:alice attendee:self
[/] S available person:alice state:available from:2026-07-24T09:00
"""


class PersonOverviewTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def overview(self, name):
        return people.person_overview(self.items, CONFIG, name, TODAY)

    def test_counts(self):
        ov = self.overview("alice")
        self.assertEqual(2, ov["counts"]["assigned_open"])  # Design + WaitReply
        self.assertEqual(1, ov["counts"]["waiting"])
        self.assertEqual(1, ov["counts"]["overdue"])
        self.assertEqual(1, ov["counts"]["messages_sent"])
        self.assertEqual(1, ov["counts"]["messages_received"])
        self.assertEqual(1, ov["counts"]["meetings"])

    def test_presence_resolved(self):
        ov = self.overview("alice")
        self.assertIsNotNone(ov["presence"])
        self.assertEqual("available", ov["presence"]["state"])

    def test_memberships(self):
        ov = self.overview("alice")
        self.assertEqual(["platform"], ov["memberships"]["teams"])
        self.assertEqual(["eng"], ov["memberships"]["groups"])

    def test_projects_owner(self):
        ov = self.overview("alice")
        self.assertEqual("web", ov["projects"][0]["name"])
        self.assertTrue(ov["projects"][0]["owner"])

    def test_alias_resolution(self):
        # "me" resolves to self; MyTask is assigned to me.
        ov = people.person_overview(self.items, CONFIG, "me", TODAY)
        self.assertEqual("self", ov["person"])
        self.assertEqual(1, ov["counts"]["assigned_open"])

    def test_resolve_person(self):
        self.assertEqual("self", people.resolve_person(CONFIG, "me"))
        self.assertEqual("bob", people.resolve_person(CONFIG, "bob"))


class PeopleListTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_list_aggregates(self):
        rows = {r["person"]: r for r in people.people_list(self.items, CONFIG, TODAY)}
        self.assertIn("alice", rows)
        self.assertIn("bob", rows)
        self.assertEqual(2, rows["alice"]["assigned_open"])

    def test_alias_folds_into_canonical(self):
        rows = {r["person"]: r for r in people.people_list(self.items, CONFIG, TODAY)}
        # MyTask assigned to "me" folds into "self".
        self.assertIn("self", rows)
        self.assertNotIn("me", rows)


class GroupOverviewTests(unittest.TestCase):
    def setUp(self):
        self.items, _ = parse_text(SAMPLE)

    def test_group_overview_aggregates_members(self):
        report = people.group_overview(self.items, CONFIG, "eng", TODAY)
        self.assertEqual(2, report["member_count"])
        members = {m["person"]: m for m in report["members"]}
        self.assertEqual(2, members["alice"]["assigned_open"])
        self.assertEqual(2, report["total_assigned_open"])
        self.assertEqual(1, report["total_overdue"])

    def test_unknown_group_raises(self):
        with self.assertRaises(ValueError):
            people.group_overview(self.items, CONFIG, "nope", TODAY)


if __name__ == "__main__":
    unittest.main()
