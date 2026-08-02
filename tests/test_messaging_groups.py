import unittest

from lifetxt.parser import parse_text
from lifetxt import groups, delivery


CONFIG = {
    "teams": {"platform": {"members": ["carol", "dave"]}},
    "groups": {
        "oncall": {"members": ["alice", "bob"], "disabled_members": ["bob"]},
        "eng": {"members": ["oncall", "team:platform", "alice"]},
        "aliased": {"members": ["erin"], "aliases": ["a1"]},
        "loop1": {"members": ["loop2"]},
        "loop2": {"members": ["loop1"]},
        "empty": {"members": []},
    },
}


class GroupExpansionTests(unittest.TestCase):
    def test_nested_expansion_dedupes_and_orders(self):
        result = groups.resolve_recipients(CONFIG, ["group:eng"])
        self.assertEqual(["alice", "carol", "dave"], result["recipients"])
        self.assertEqual([], result["diagnostics"])

    def test_disabled_member_excluded(self):
        members = groups.expand_group(CONFIG, "oncall")
        self.assertEqual(["alice"], members)

    def test_team_reference_expanded(self):
        result = groups.resolve_recipients(CONFIG, ["team:platform"])
        self.assertEqual(["carol", "dave"], result["recipients"])

    def test_mixed_direct_and_group_dedupe(self):
        result = groups.resolve_recipients(CONFIG, ["alice", "group:oncall", "erin"])
        self.assertEqual(["alice", "erin"], result["recipients"])

    def test_cycle_detected(self):
        diags = []
        groups.expand_group(CONFIG, "loop1", diagnostics=diags)
        self.assertTrue(any(d["code"] == "G002" for d in diags))

    def test_unknown_group(self):
        result = groups.resolve_recipients(CONFIG, ["group:ghost"])
        self.assertTrue(any(d["code"] == "G001" for d in result["diagnostics"]))

    def test_alias_resolves(self):
        result = groups.resolve_recipients(CONFIG, ["a1"])
        self.assertEqual(["erin"], result["recipients"])

    def test_validate_reports_cycles_and_empty(self):
        rows = groups.validate_groups(CONFIG)
        codes = {r["code"] for r in rows}
        self.assertIn("G002", codes)
        self.assertIn("G003", codes)  # empty group

    def test_expansion_map_preserves_references(self):
        result = groups.resolve_recipients(CONFIG, ["group:eng", "zoe"])
        self.assertEqual(["alice", "carol", "dave"], result["expansion"]["group:eng"])
        self.assertEqual(["zoe"], result["expansion"]["zoe"])

    def test_summaries(self):
        summaries = {s["name"]: s for s in groups.group_summaries(CONFIG)}
        self.assertEqual(1, summaries["oncall"]["resolved_members"])
        self.assertFalse(summaries["loop1"]["ok"])


class DeliveryStateTests(unittest.TestCase):
    def message(self, line):
        items, _ = parse_text("#! timezone: UTC\n%s\n" % line)
        return items[0]

    def test_states_from_ack_and_read(self):
        item = self.message(
            "[ ] M Ship sender:alice recipient:alice recipient:carol recipient:dave "
            "ack:alice read:carol id:M-1"
        )
        states = {s["recipient"]: s["state"] for s in delivery.delivery_states(item)}
        self.assertEqual("acknowledged", states["alice"])
        self.assertEqual("read", states["carol"])
        self.assertEqual("pending", states["dave"])

    def test_skipped_recipient(self):
        item = self.message("[ ] M X sender:a recipient:bob skip:bob id:M-2")
        states = {s["recipient"]: s["state"] for s in delivery.delivery_states(item)}
        self.assertEqual("skipped", states["bob"])

    def test_ack_policy_all_incomplete(self):
        item = self.message(
            "[ ] M X sender:a recipient:carol recipient:dave ack:carol ack_policy:all id:M-3"
        )
        status = delivery.acknowledgement_status(item)
        self.assertEqual("all", status["policy"])
        self.assertEqual(2, status["required"])
        self.assertFalse(status["complete"])
        self.assertEqual(["dave"], status["pending"])

    def test_ack_policy_any_complete(self):
        item = self.message(
            "[ ] M X sender:a recipient:carol recipient:dave ack:carol ack_policy:any id:M-4"
        )
        self.assertTrue(delivery.acknowledgement_status(item)["complete"])

    def test_ack_policy_count(self):
        item = self.message(
            "[ ] M X sender:a recipient:a recipient:b recipient:c ack:a ack:b ack_policy:2 id:M-5"
        )
        status = delivery.acknowledgement_status(item)
        self.assertEqual(2, status["required"])
        self.assertTrue(status["complete"])

    def test_skipped_excluded_from_all_policy(self):
        item = self.message(
            "[ ] M X sender:a recipient:carol recipient:dave ack:carol skip:dave "
            "ack_policy:all id:M-6"
        )
        status = delivery.acknowledgement_status(item)
        self.assertEqual(1, status["effective_total"])
        self.assertTrue(status["complete"])

    def test_resolver_expands_group_recipients(self):
        item = self.message("[ ] M X sender:a recipient:group_placeholder id:M-7")
        # With a resolver, recipient values could expand; here we pass the
        # groups resolver with a config that maps the literal to itself.
        summary = delivery.delivery_summary(
            item, config=CONFIG, resolver=groups.resolve_recipients
        )
        self.assertEqual(1, summary["recipient_count"])


if __name__ == "__main__":
    unittest.main()
