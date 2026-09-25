import os
import tempfile
import unittest
from unittest import mock

from lifetxt.remote_access import RemoteAccessError, principal_registry
from lifetxt.remote_backend import snapshot

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None

from lifetxt.webapp import create_app


class RemoteWorkspaceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.primary = os.path.join(self.temp.name, "primary.life.txt")
        self.generated = os.path.join(self.temp.name, "calendar.life.txt")
        with open(self.primary, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Visible id:I-1 project:home visibility:shared\n")
        with open(self.generated, "w", encoding="utf-8") as handle:
            handle.write("[ ] E Generated id:I-2 project:home visibility:shared\n")
        self.config = {
            "_path": os.path.join(self.temp.name, "config.json"),
            "_active_workspace": "personal",
            "workspaces": {
                "personal": {
                    "sources": [
                        {"path": "primary.life.txt", "role": "primary"},
                        {"path": "calendar.life.txt", "role": "generated"},
                    ],
                    "write_file": "primary.life.txt",
                }
            },
            "remote": {
                "enabled": True,
                "principals": [{"id": "alice", "role": "reader"}],
            },
        }
        self.principal = principal_registry(self.config)["alice"]

    def tearDown(self):
        self.temp.cleanup()

    def test_v2_manifest_is_opaque_role_aware_and_contains_items(self):
        value = snapshot(
            [self.primary, self.generated],
            self.config,
            self.principal,
            protocol_version=2,
            writable_path=self.primary,
        )

        self.assertEqual(64, len(value["workspace"]["workspace_id"]))
        self.assertEqual(2, len(value["workspace"]["sources"]))
        self.assertEqual(
            ["primary", "generated"],
            [row["role"] for row in value["workspace"]["sources"]],
        )
        self.assertEqual(
            [True, False],
            [row["writable"] for row in value["workspace"]["sources"]],
        )
        self.assertEqual(
            value["workspace"]["sources"][0]["source_id"],
            value["workspace"]["write_source_id"],
        )
        self.assertEqual(["I-1", "I-2"], [row["id"] for row in value["items"]])
        rendered = str(value)
        self.assertNotIn(self.temp.name, rendered)
        self.assertNotIn("primary.life.txt", rendered)
        self.assertNotIn("calendar.life.txt", rendered)

    def test_v1_snapshot_shape_remains_legacy(self):
        value = snapshot(
            [self.primary], self.config, self.principal, writable_path=self.primary
        )
        self.assertNotIn("workspace", value)
        self.assertNotIn("items", value)

    def test_manifest_identity_is_stable_across_server_path_relocation(self):
        first = snapshot(
            [self.primary],
            self.config,
            self.principal,
            protocol_version=2,
            writable_path=self.primary,
        )["workspace"]["workspace_id"]
        relocated = dict(self.config)
        relocated["_path"] = os.path.join(self.temp.name, "elsewhere", "config.json")
        second = snapshot(
            [self.primary],
            relocated,
            self.principal,
            protocol_version=2,
            writable_path=self.primary,
        )["workspace"]["workspace_id"]
        self.assertEqual(first, second)

    def test_snapshot_rejects_a_mid_read_revision_change(self):
        with mock.patch(
            "lifetxt.remote_backend.source_revision", side_effect=["a" * 64, "b" * 64]
        ):
            with self.assertRaises(RemoteAccessError) as caught:
                snapshot(
                    [self.primary],
                    self.config,
                    self.principal,
                    protocol_version=2,
                    writable_path=self.primary,
                )
        self.assertEqual("REMOTE_SNAPSHOT_REVISION_CHANGED", caught.exception.code)
        self.assertEqual(409, caught.exception.status)
        self.assertNotIn("a" * 64, str(caught.exception.detail))

    def test_duplicate_ids_are_reported_without_disclosing_the_id(self):
        with open(self.primary, "a", encoding="utf-8") as handle:
            handle.write("[ ] T Duplicate id:I-1 visibility:shared\n")
        value = snapshot(
            [self.primary],
            self.config,
            self.principal,
            protocol_version=2,
            writable_path=self.primary,
        )
        self.assertIn(
            {"severity": "warning", "code": "W213", "count": 1},
            value["workspace"]["diagnostics"],
        )
        self.assertNotIn("Duplicate ID", str(value["workspace"]["diagnostics"]))


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteWorkspaceSnapshotWebTests(unittest.TestCase):
    def setUp(self):
        os.environ["REMOTE_SNAPSHOT_TOKEN"] = "snapshot-secret"
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "life.txt")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Visible id:I-1 visibility:shared\n")
        self.config = {
            "paths": [self.path],
            "write_file": self.path,
            "remote": {
                "enabled": True,
                "allow_loopback_http": True,
                "principals": [
                    {
                        "id": "alice",
                        "role": "reader",
                        "token_env": "REMOTE_SNAPSHOT_TOKEN",
                    }
                ],
            },
        }
        self.client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=self.config,
                read_only=True,
            )
        )

    def tearDown(self):
        self.temp.cleanup()
        os.environ.pop("REMOTE_SNAPSHOT_TOKEN", None)

    def test_v2_capability_and_snapshot_advertise_the_contract(self):
        headers = {
            "Authorization": "Bearer snapshot-secret",
            "X-Lifetxt-Remote-Version": "2",
        }
        capability = self.client.get("/api/remote/v1/capabilities", headers=headers)
        self.assertEqual(200, capability.status_code)
        self.assertIn("workspace-sync-snapshot", capability.json()["features"])
        response = self.client.get("/api/remote/v1/snapshot", headers=headers)
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn("workspace", response.json())
        self.assertEqual(["I-1"], [row["id"] for row in response.json()["items"]])
        self.assertNotIn(self.temp.name, response.text)

    def test_snapshot_requires_read_scope(self):
        response = self.client.get(
            "/api/remote/v1/snapshot",
            headers={"X-Lifetxt-Remote-Version": "2"},
        )
        self.assertEqual(401, response.status_code)


if __name__ == "__main__":
    unittest.main()
