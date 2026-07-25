from __future__ import unicode_literals

import base64
import os
import tempfile
import unittest
from datetime import datetime, timezone

from lifetxt import mcp, mutation, webapp
from lifetxt.attachment_transactions import attachment_revision, directory_revision
from lifetxt.mcp import McpContext


class RemoteAttachmentContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.life = os.path.join(self.root, "life.txt")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Task id:t1\n")
        self.source = os.path.join(self.root, "source")
        os.makedirs(self.source)
        with open(os.path.join(self.source, "a.txt"), "w", encoding="utf-8") as handle:
            handle.write("alpha")
        self.config = {
            "attachments": {
                "root": self.root,
                "remote_source_root": self.root,
                "max_files": 20,
                "max_bytes": 1024 * 1024,
                "max_file_bytes": 1024 * 1024,
                "remote_chunk_bytes": 4,
            },
            "transactions": {"journal_dir": os.path.join(self.root, "journals")},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_web_directory_package_chunk_manifest_and_status(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test dependencies unavailable")
        client = TestClient(webapp.create_app([self.life], writable_path=self.life, config=self.config))
        item_revision = mutation.read_text_snapshot(self.life).content_hash
        response = client.post("/api/attachments/directory-reference", json={
            "id": "t1",
            "path": "./source",
            "item_revision": item_revision,
            "attachment_revision": directory_revision(self.source, config=self.config),
        })
        self.assertEqual(200, response.status_code, response.text)
        item_revision = response.json()["item_revision"]
        response = client.post("/api/attachments/package", json={
            "id": "t1",
            "source": "./source",
            "path": "./bundle.zip",
            "item_revision": item_revision,
            "attachment_revision": mutation.MISSING_HASH,
            "transaction_id": "web-package-1",
        })
        self.assertEqual(200, response.status_code, response.text)
        package_revision = response.json()["attachment_revision"]
        inspected = client.get("/api/attachments/package-manifest", params={
            "path": "./bundle.zip", "attachment_revision": package_revision,
        })
        self.assertEqual(200, inspected.status_code, inspected.text)
        self.assertTrue(inspected.json()["ok"])
        chunk = client.get("/api/attachments/chunk", params={
            "path": "./bundle.zip", "limit": 8, "attachment_revision": package_revision,
        })
        self.assertEqual(200, chunk.status_code, chunk.text)
        self.assertEqual(4, len(base64.b64decode(chunk.json()["content_base64"])))
        self.assertEqual(4, chunk.json()["limit"])
        status = client.get("/api/attachments/transactions/web-package-1")
        self.assertEqual(200, status.status_code)
        self.assertTrue(status.json()["found"])
        self.assertEqual("committed", status.json()["state"])
        duplicate = client.post("/api/attachments/package", json={
            "id": "t1",
            "source": "./source",
            "path": "./bundle.zip",
            "item_revision": response.json()["item_revision"],
            "attachment_revision": package_revision,
            "transaction_id": "web-package-1",
        })
        self.assertEqual(409, duplicate.status_code)
        self.assertEqual("DUPLICATE_TRANSACTION_ID", duplicate.json()["error"])

    def test_mcp_remote_clock_and_package_contract(self):
        config = dict(self.config)
        config["clock"] = {
            "require_remote_write_time": True,
            "skew_warning_seconds": 10 ** 10,
            "skew_reject_seconds": 10 ** 11,
        }
        context = McpContext(paths=[self.life], writable_path=self.life, config=config)
        capabilities = mcp.call_tool("get_capabilities", {}, context)
        self.assertTrue(capabilities["remote_clock"]["required_for_writes"])
        self.assertEqual(4, capabilities["attachment_contract"]["max_chunk_bytes"])
        missing = mcp.call_tool("attachment_package", {
            "id": "t1", "source": "./source", "path": "./mcp.zip",
            "item_revision": mutation.read_text_snapshot(self.life).content_hash,
            "attachment_revision": mutation.MISSING_HASH,
            "transaction_id": "mcp-package-1",
        }, context)
        self.assertEqual("CLIENT_TIME_REQUIRED", missing["error"])
        result = mcp.call_tool("attachment_package", {
            "id": "t1", "source": "./source", "path": "./mcp.zip",
            "item_revision": mutation.read_text_snapshot(self.life).content_hash,
            "attachment_revision": mutation.MISSING_HASH,
            "transaction_id": "mcp-package-1",
            "client_time": "2026-07-25T03:00:00Z",
        }, context)
        self.assertEqual("package", result["action"])
        self.assertIn("clock", result)
        state = mcp.call_tool("attachment_transaction_status", {"transaction_id": "mcp-package-1"}, context)
        self.assertTrue(state["found"])
        schemas = {row["name"]: row for row in mcp.tool_schemas()}
        self.assertIn("attachment_read_chunk", schemas)
        self.assertTrue(schemas["attachment_read_chunk"]["annotations"]["readOnlyHint"])


    def test_web_clock_guard_capabilities_and_parser_exception(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test dependencies unavailable")
        config = dict(self.config)
        config["clock"] = {
            "require_remote_write_time": True,
            "skew_warning_seconds": 60,
            "skew_reject_seconds": 300,
        }
        client = TestClient(webapp.create_app([self.life], writable_path=self.life, config=config))
        capabilities = client.get("/api/capabilities")
        self.assertTrue(capabilities.json()["remote_clock"]["required_for_writes"])
        self.assertEqual("X-Lifetxt-Client-Time", capabilities.json()["remote_clock"]["client_time_header"])

        parser = client.post("/api/check-line", json={"line": "[ ] T Parsed id:p1"})
        self.assertEqual(200, parser.status_code, parser.text)

        revision = client.get("/api/items").headers["etag"]
        missing = client.post(
            "/api/items", headers={"If-Match": revision},
            json={"status": "[ ]", "type": "T", "title": "Missing clock", "details": {}},
        )
        self.assertEqual(428, missing.status_code, missing.text)
        self.assertEqual("CLIENT_TIME_REQUIRED", missing.json()["error"])

        rejected = client.post(
            "/api/items",
            headers={"If-Match": revision, "X-Lifetxt-Client-Time": "2000-01-01T00:00:00Z"},
            json={"status": "[ ]", "type": "T", "title": "Old clock", "details": {}},
        )
        self.assertEqual(409, rejected.status_code, rejected.text)
        self.assertEqual("CLOCK_SKEW", rejected.json()["error"])

        accepted = client.post(
            "/api/items",
            headers={
                "If-Match": revision,
                "X-Lifetxt-Client-Time": datetime.now(timezone.utc).isoformat(),
            },
            json={"status": "[ ]", "type": "T", "title": "Clock safe", "details": {}},
        )
        self.assertEqual(201, accepted.status_code, accepted.text)
        self.assertEqual("ok", accepted.headers["X-Lifetxt-Clock-State"])

    def test_all_writable_mcp_schemas_publish_client_time(self):
        schemas = {row["name"]: row for row in mcp.tool_schemas()}
        for name, schema in schemas.items():
            properties = schema["inputSchema"].get("properties", {})
            if name in mcp.READ_ONLY_TOOLS:
                continue
            self.assertIn("client_time", properties, name)

    def test_remote_package_source_escape_is_rejected(self):
        outside = os.path.join(self.root, "..", "outside-source")
        os.makedirs(outside, exist_ok=True)
        context = McpContext(paths=[self.life], writable_path=self.life, config=self.config)
        with self.assertRaises(ValueError):
            mcp.call_tool("attachment_package", {
                "id": "t1", "source": "../outside-source", "path": "./bad.zip",
                "item_revision": mutation.read_text_snapshot(self.life).content_hash,
                "attachment_revision": mutation.MISSING_HASH,
                "transaction_id": "escape-1",
            }, context)


if __name__ == "__main__":
    unittest.main()
