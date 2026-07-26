import unittest

from lifetxt.safety_foundation import schema_bundle


class SchemaExtensionsV22Tests(unittest.TestCase):
    def test_remote_ticket_mutation_schema_is_published(self):
        bundle = schema_bundle()
        self.assertIn("remote-ticket-mutation-v1.schema.json", bundle)
        schema = bundle["remote-ticket-mutation-v1.schema.json"]
        self.assertEqual(
            "https://github.com/Eruhitsuji/lifetxt/raw/main/dist/schemas/remote-ticket-mutation-v1.schema.json",
            schema["$id"],
        )
        self.assertIn("transaction_id", schema["required"])


if __name__ == "__main__":
    unittest.main()
