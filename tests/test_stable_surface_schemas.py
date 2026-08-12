from __future__ import annotations

import os
import tempfile
import unittest

from jsonschema import Draft202012Validator

from lifetxt.mcp import McpContext, call_tool
from lifetxt.safety_foundation import schema_bundle

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


@unittest.skipIf(TestClient is None, "web extras unavailable")
class StableSurfaceSchemaTests(unittest.TestCase):
    """Validate the bounded read-only Web/MCP envelope slice for #404."""

    def setUp(self):
        from lifetxt.webapp import create_app

        self.temp_dir = tempfile.TemporaryDirectory(prefix="lifetxt-schema-")
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("[ ] T Alpha\n")
        self.client = TestClient(
            create_app(paths=[self.path], writable_path=self.path)
        )
        bundle = schema_bundle()
        self.item_validator = Draft202012Validator(bundle["item-v1.schema.json"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def _assert_envelope(self, response):
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertIsInstance(body["items"], list)
        for item in body["items"]:
            self.assertIsNone(next(iter(self.item_validator.iter_errors(item)), None))
        for diagnostic in body["diagnostics"]:
            self.assertEqual(
                {"severity", "code", "category", "message", "line", "hint"},
                set(diagnostic),
            )
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
            self.assertEqual(
                {"severity", "code", "category", "message", "line", "hint"},
                set(diagnostic),
            )

        with open(self.path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write('[ ] T "Unclosed title\n')
        invalid = call_tool("list_items", {}, context)
        self.assertTrue(any(row["severity"] == "error" for row in invalid["diagnostics"]))


if __name__ == "__main__":
    unittest.main()
