from __future__ import annotations

import os
import tempfile
import unittest

try:
    from jsonschema import Draft202012Validator
except Exception:
    Draft202012Validator = None

from lifetxt.mcp import McpContext, call_tool
from lifetxt.safety_foundation import schema_bundle

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


@unittest.skipIf(
    TestClient is None or Draft202012Validator is None,
    "Web extras or jsonschema unavailable",
)
class StableSurfaceSchemaTests(unittest.TestCase):
    """Validate the bounded read-only Web/MCP envelope slice for #404."""

    def setUp(self):
        from lifetxt.webapp import create_app

        self.temp_dir = tempfile.TemporaryDirectory(prefix="lifetxt-schema-")
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Alpha id:alpha\n")
        self.client = TestClient(
            create_app(paths=[self.path], writable_path=self.path)
        )
        bundle = schema_bundle()
        item_schema = bundle["item-v1.schema.json"]
        self.assertTrue(item_schema["$id"].endswith("item-v1.schema.json"))
        self.assertEqual("lifetxt item v1", item_schema["title"])
        self.item_validator = Draft202012Validator(item_schema)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _assert_envelope(self, response):
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsInstance(body["items"], list)
        for item in body["items"]:
            self.assertIsNone(next(iter(self.item_validator.iter_errors(item)), None))
        for diagnostic in body["diagnostics"]:
            self.assertTrue(
                set(diagnostic) <= {
                    "severity",
                    "code",
                    "category",
                    "message",
                    "source",
                    "line",
                    "column",
                    "span",
                    "hint",
                }
            )
            self.assertTrue({"severity", "code", "message", "hint"} <= set(diagnostic))
        return body

    def test_web_read_envelope_validates_success_and_diagnostics(self):
        success = self._assert_envelope(self.client.get("/api/items"))
        self.assertEqual(1, success["count"])

        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write('[ ] T "Unclosed title\n')
        invalid = self._assert_envelope(self.client.get("/api/items"))
        self.assertTrue(any(row["severity"] == "error" for row in invalid["diagnostics"]))

    def test_mcp_read_envelope_validates_success_and_diagnostics(self):
        context = McpContext(paths=[self.path], writable_path=self.path)
        success = call_tool("list_items", {}, context)
        self.assertEqual(1, success["count"])
        for item in success["items"]:
            self.assertIsNone(next(iter(self.item_validator.iter_errors(item)), None))
        for diagnostic in success["diagnostics"]:
            self.assertTrue(
                set(diagnostic) <= {
                    "severity",
                    "code",
                    "category",
                    "message",
                    "source",
                    "line",
                    "column",
                    "span",
                    "hint",
                }
            )
            self.assertTrue({"severity", "code", "message", "hint"} <= set(diagnostic))

        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write('[ ] T "Unclosed title\n')
        invalid = call_tool("list_items", {}, context)
        self.assertTrue(any(row["severity"] == "error" for row in invalid["diagnostics"]))

    def test_web_and_mcp_single_item_reads_validate_item_v1(self):
        web = self.client.get("/api/items/1")
        self.assertEqual(200, web.status_code)
        web_item = web.json()["item"]
        self.assertIsNone(next(iter(self.item_validator.iter_errors(web_item)), None))

        context = McpContext(paths=[self.path], writable_path=self.path)
        mcp = call_tool("get_item", {"id": "alpha"}, context)
        self.assertIsNone(
            next(iter(self.item_validator.iter_errors(mcp["item"])), None)
        )
        self.assertEqual("alpha", mcp["item"]["id"])

    def test_schema_version_and_compatibility_boundary_are_explicit(self):
        bundle = schema_bundle()
        diagnostic_schema = bundle["diagnostic-v1.schema.json"]
        self.assertTrue(diagnostic_schema["$id"].endswith("diagnostic-v1.schema.json"))
        self.assertEqual("lifetxt diagnostic v1", diagnostic_schema["title"])
        self.assertFalse(diagnostic_schema["additionalProperties"])
        self.assertEqual("1", bundle["item-v1.schema.json"]["$id"].rsplit("-v", 1)[1].split(".", 1)[0])

    def test_web_read_error_envelope_is_stable(self):
        response = self.client.get("/api/items/id/missing")
        self.assertEqual(404, response.status_code)
        self.assertEqual(
            {"error": "NOT_FOUND", "message": "Item id:missing was not found.", "detail": None},
            response.json(),
        )


if __name__ == "__main__":
    unittest.main()
