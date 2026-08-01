import importlib.util
import json
import os
import tempfile
import unittest

from lifetxt import mcp, webapp
from lifetxt.doctor import doctor_report
from lifetxt.mcp import McpContext
from lifetxt.release_policy import schema_validation_report
from lifetxt.safety_foundation import schema_bundle


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def has_draft_2020_validator():
    try:
        from jsonschema import Draft202012Validator  # noqa: F401
        from referencing import Registry, Resource  # noqa: F401
    except ImportError:
        return False
    return True


class SchemaExtensionsV2Tests(unittest.TestCase):
    def test_bundle_contains_seventy_six_generated_and_published_documents(self):
        bundle = schema_bundle()
        self.assertEqual(76, len(bundle))
        for name, generated in bundle.items():
            path = os.path.join(ROOT, "dist", "schemas", name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, "r", encoding="utf-8") as handle:
                self.assertEqual(generated, json.load(handle), name)

    def test_release_schema_gate_resolves_local_references(self):
        optional = schema_validation_report(ROOT, require_validator=False)
        self.assertTrue(optional["ok"], optional)
        if optional["validator_available"]:
            strict = schema_validation_report(ROOT, require_validator=True)
            self.assertTrue(strict["ok"], strict)
            self.assertEqual(76, strict["schema_count"])
            self.assertEqual(76, strict["sample_count"])
            self.assertEqual("network-free referencing.Registry over published bundle", strict["reference_resolution"])

    @unittest.skipUnless(has_draft_2020_validator(), "Draft 2020-12 jsonschema validation not available")
    def test_real_doctor_report_validates_with_references(self):
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource

        with tempfile.TemporaryDirectory() as directory:
            life = os.path.join(directory, "life.txt")
            metrics = os.path.join(directory, "metrics.json")
            with open(life, "w", encoding="utf-8") as handle:
                handle.write("#! timezone: UTC\n[ ] T Task id:T-1\n")
            report = doctor_report(
                [life],
                config={"defaults": {"timezone": "UTC"}},
                revision_metrics_path=metrics,
            )
            bundle = schema_bundle()
            schema = bundle["doctor-v1.schema.json"]
            registry = Registry()
            for name, value in bundle.items():
                resource = Resource.from_contents(value)
                registry = registry.with_resource(name, resource)
                registry = registry.with_resource(value["$id"], resource)
            validator = Draft202012Validator(schema, registry=registry)
            errors = list(validator.iter_errors(report))
            self.assertEqual([], errors)


@unittest.skipUnless(
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None
    and has_draft_2020_validator(),
    "Web/schema dependencies are not installed.",
)
class RealCapabilitySchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:T-1\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def validate_capability(self, value):
        from jsonschema import Draft202012Validator

        schema = schema_bundle()["capability-v1.schema.json"]
        errors = list(Draft202012Validator(schema).iter_errors(value))
        self.assertEqual([], errors)

    def test_actual_web_capability_response_validates(self):
        from fastapi.testclient import TestClient

        client = TestClient(webapp.create_app(paths=[self.path], writable_path=self.path))
        response = client.get("/api/capabilities")
        self.assertEqual(200, response.status_code)
        self.validate_capability(response.json())

    def test_actual_mcp_tool_and_resource_capabilities_validate_and_match(self):
        context = McpContext(paths=[self.path], writable_path=self.path)
        tool_response = mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_capabilities", "arguments": {}},
            },
            context,
        )
        tool = tool_response["result"]["structuredContent"]
        resource_response = mcp.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/read",
                "params": {"uri": "lifetxt://capabilities"},
            },
            context,
        )
        resource_text = resource_response["result"]["contents"][0]["text"]
        resource = json.loads(resource_text)
        self.validate_capability(tool)
        self.validate_capability(resource)
        self.assertEqual(tool, resource)


if __name__ == "__main__":
    unittest.main()
