import unittest

from lifetxt.remote_access import capability
from lifetxt.remote_compatibility_v21 import evaluate_compatibility
from lifetxt.safety_foundation import schema_bundle


class RemoteCompatibilityV21Tests(unittest.TestCase):
    def test_v2_capability_publishes_expanded_manifest(self):
        first = capability({"remote": {"enabled": True}}, 2)
        second = capability({"remote": {"enabled": True}}, 2)
        self.assertEqual("lifetxt", first["server"]["package"])
        self.assertEqual(len(schema_bundle()), first["schema_bundle"]["document_count"])
        self.assertEqual(64, len(first["schema_bundle"]["revision"]))
        self.assertEqual(first["capability_revision"], second["capability_revision"])
        self.assertIn("workspace_manifest", first["contracts"])
        self.assertIn("transaction_journal_policy", first["contracts"])
        self.assertIn("ticket_workflow", first["contracts"])
        self.assertIn("remote_resource", first["contracts"])
        self.assertEqual([1, 2], first["compatibility"]["supported_protocols"])
        self.assertEqual("ignore", first["compatibility"]["unknown_fields"])
        self.assertEqual({"fastapi", "uvicorn"}, set(first["optional_dependencies"]["web"]["modules"]))

    def test_client_compatibility_reports_overlap_and_legacy_metadata(self):
        value = evaluate_compatibility({
            "contract_version": "2",
            "protocol": {"minimum": 2, "current": 3},
        }, 2)
        self.assertTrue(value["ok"])
        self.assertEqual([2], value["overlap"])
        self.assertFalse(value["manifest_present"])
        self.assertTrue(value["warnings"])

        incompatible = evaluate_compatibility({
            "protocol": {"minimum": 3, "current": 4},
        }, 2)
        self.assertFalse(incompatible["ok"])
        self.assertEqual([], incompatible["overlap"])
        self.assertIsNone(incompatible["selected_protocol"])

    def test_remote_capability_schema_requires_manifest(self):
        schema = schema_bundle()["remote-capability-v2.schema.json"]
        for name in ("server", "schema_bundle", "contracts", "optional_dependencies", "compatibility"):
            self.assertIn(name, schema["required"])
            self.assertIn(name, schema["properties"])


if __name__ == "__main__":
    unittest.main()
