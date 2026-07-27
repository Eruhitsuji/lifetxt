import unittest

from lifetxt.remote_ticket_writes import enrich_capability


class RemoteTicketCapabilityV26Tests(unittest.TestCase):
    def test_protocol_v2_publishes_conservative_field_contract(self):
        value = enrich_capability(
            {"remote": {"ticket_writes_enabled": True}},
            protocol_version=2,
        )
        policy = value["mutation_policy"]
        self.assertEqual(policy["field_contract_version"], "1")
        self.assertIn("priority", policy["editable_fields"])
        self.assertIn("due", policy["editable_fields"])
        self.assertIn("ticket_id", policy["create_fields"])
        self.assertIn("subject", policy["create_fields"])
        self.assertFalse(policy["raw_source_replacement_enabled"])
        self.assertEqual(len(value["capability_revision"]), 64)

    def test_protocol_v1_does_not_publish_write_field_contract(self):
        value = enrich_capability(
            {"remote": {"ticket_writes_enabled": True}},
            protocol_version=1,
        )
        self.assertNotIn("editable_fields", value.get("mutation_policy") or {})


if __name__ == "__main__":
    unittest.main()
