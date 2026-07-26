import unittest

from lifetxt.schema_extensions_v20 import schema_bundle_v20, schema_samples_v20


class SchemaV20Tests(unittest.TestCase):
    def test_five_remote_hardening_schemas(self):
        self.assertEqual(5, len(schema_bundle_v20()))
        self.assertEqual(set(schema_bundle_v20()), set(schema_samples_v20()))
        self.assertIn("remote-capability-v2.schema.json", schema_bundle_v20())
        self.assertIn("remote-browser-session-v1.schema.json", schema_bundle_v20())
        self.assertIn("remote-read-response-v1.schema.json", schema_bundle_v20())
        self.assertIn("remote-diagnostics-v1.schema.json", schema_bundle_v20())
        self.assertIn("remote-profile-v3.schema.json", schema_bundle_v20())


if __name__ == "__main__":
    unittest.main()
