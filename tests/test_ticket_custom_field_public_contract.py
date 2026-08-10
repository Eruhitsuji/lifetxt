import unittest

from lifetxt.safety_foundation import capability_document, schema_bundle
from lifetxt.ticket_custom_fields import SUPPORTED_TYPES, ticket_custom_field_contract


class TicketCustomFieldPublicContractTests(unittest.TestCase):
    def test_supported_types_and_schema_are_published(self):
        self.assertEqual(
            (
                "string",
                "integer",
                "number",
                "boolean",
                "date",
                "datetime",
                "duration",
                "enum",
            ),
            SUPPORTED_TYPES,
        )
        bundle = schema_bundle()
        self.assertIn("ticket-custom-field-registry-v1.schema.json", bundle)
        self.assertIn("ticket-workflow-v1.schema.json", bundle)
        self.assertIn("ticket-activity-v1.schema.json", bundle)
        self.assertIn("ticket-planning-v1.schema.json", bundle)
        self.assertEqual(77, len(bundle))

    def test_capability_keeps_unknown_keys_and_remote_writes_safe(self):
        config = {
            "ticketing": {
                "custom_fields": {
                    "risk_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 10,
                        "filterable": True,
                        "privacy": "internal",
                    }
                }
            }
        }
        contract = ticket_custom_field_contract(config)
        self.assertTrue(contract["unknown_unconfigured_keys_allowed"])
        self.assertFalse(contract["remote_write_enforcement"])
        self.assertTrue(contract["definitions"]["risk_score"]["filterable"])
        self.assertIn("ticket_custom_fields", capability_document(config=config))


if __name__ == "__main__":
    unittest.main()
