import json
import os
import tempfile
import unittest

from lifetxt.config import load_config
from lifetxt.config_writer import config_revision, write_config
from lifetxt.webapp import create_app

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "web extras unavailable")
class RemoteCollaborationAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "team.life.txt")
        self.config_path = os.path.join(self.temp.name, "config.json")
        self.audit_path = os.path.join(self.temp.name, "remote-audit.jsonl")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Existing id:I-1 visibility:shared\n")
        for env, token in (
            ("COLLAB_OWNER_TOKEN", "owner-secret"),
            ("COLLAB_EDITOR_TOKEN", "editor-secret"),
            ("COLLAB_VIEWER_TOKEN", "viewer-secret"),
        ):
            os.environ[env] = token
        self.config = {
            "config_version": 1,
            "default_workspace": "team",
            "workspaces": {
                "team": {
                    "sources": [self.path],
                    "write_file": self.path,
                    "collaboration": {
                        "members": {
                            "alice": {"role": "owner"},
                            "bob": {"role": "editor"},
                            "carol": {"role": "viewer"},
                        }
                    },
                }
            },
            "remote": {
                "enabled": True,
                "item_writes_enabled": True,
                "allow_loopback_http": True,
                "audit_log": self.audit_path,
                "principals": [
                    {
                        "id": "alice",
                        "role": "reader",
                        "scopes": ["write", "admin"],
                        "token_env": "COLLAB_OWNER_TOKEN",
                    },
                    {
                        "id": "bob",
                        "role": "reader",
                        "scopes": ["write", "admin"],
                        "token_env": "COLLAB_EDITOR_TOKEN",
                    },
                    {
                        "id": "carol",
                        "role": "reader",
                        "scopes": ["write", "admin"],
                        "token_env": "COLLAB_VIEWER_TOKEN",
                    },
                    {"id": "dave", "role": "reader", "scopes": ["read", "write"]},
                ],
            },
        }
        write_config(self.config_path, self.config)
        self.config = load_config(self.config_path)
        self.client = TestClient(
            create_app(paths=[self.path], writable_path=self.path, config=self.config)
        )
        self.v2 = {"X-Lifetxt-Remote-Version": "2"}
        self.owner = dict(self.v2, Authorization="Bearer owner-secret")
        self.editor = dict(self.v2, Authorization="Bearer editor-secret")
        self.viewer = dict(self.v2, Authorization="Bearer viewer-secret")

    def tearDown(self):
        self.temp.cleanup()
        for env in (
            "COLLAB_OWNER_TOKEN",
            "COLLAB_EDITOR_TOKEN",
            "COLLAB_VIEWER_TOKEN",
        ):
            os.environ.pop(env, None)

    def roster(self, headers=None):
        return self.client.get(
            "/api/remote/v1/workspace/members?workspace=team",
            headers=headers or self.owner,
        )

    def mutate(self, operation, principal_id, role=None, revision=None, headers=None):
        payload = {
            "workspace": "team",
            "operation": operation,
            "principal_id": principal_id,
            "expected_config_revision": revision,
        }
        if role is not None:
            payload["role"] = role
        return self.client.post(
            "/api/remote/v1/workspace/members",
            headers=headers or self.owner,
            json=payload,
        )

    def test_owner_can_list_and_change_members_with_config_cas(self):
        capability = self.client.get(
            "/api/remote/v1/capabilities", headers=self.owner
        ).json()
        self.assertTrue(capability["workspace_membership_admin"]["available"])
        capability_response = self.client.get(
            "/api/remote/v1/capabilities", headers=self.owner
        )
        self.assertEqual(
            capability_response.json()["capability_revision"],
            capability_response.headers["X-Lifetxt-Remote-Capability-Revision"],
        )
        listing = self.roster()
        self.assertEqual(200, listing.status_code, listing.text)
        value = listing.json()
        self.assertEqual(64, len(value["config_revision"]))
        self.assertEqual(
            {"alice", "bob", "carol"}, {row["principal_id"] for row in value["members"]}
        )
        self.assertNotIn("token_env", listing.text)
        self.assertNotIn("admin", listing.text)
        self.assertNotIn(self.temp.name, listing.text)

        response = self.mutate("role", "carol", "editor", value["config_revision"])
        self.assertEqual(200, response.status_code, response.text)
        self.assertNotEqual(value["config_revision"], response.json()["revision_after"])
        self.assertEqual(
            "editor",
            self.client.get("/api/remote/v1/snapshot", headers=self.viewer).json()[
                "workspace"
            ]["collaboration"]["role"],
        )

    def test_non_owner_and_owner_without_scope_cannot_manage_members(self):
        self.assertEqual(403, self.roster(self.editor).status_code)
        revision = self.roster().json()["config_revision"]
        current = load_config(self.config_path)
        current["remote"]["principals"][0]["scopes"] = ["read", "write"]
        write_config(
            self.config_path,
            current,
            expected_revision=revision,
            require_revision=True,
        )
        self.client = TestClient(
            create_app(
                paths=[self.path],
                writable_path=self.path,
                config=load_config(self.config_path),
            )
        )
        self.assertEqual(403, self.roster(self.owner).status_code)

    def test_self_demotion_and_removal_are_allowed_when_another_owner_remains(self):
        with open(self.path, encoding="utf-8") as handle:
            original_items = handle.read()
        revision = self.roster().json()["config_revision"]
        promote = self.mutate("role", "bob", "owner", revision)
        self.assertEqual(200, promote.status_code, promote.text)
        bob = dict(self.v2, Authorization="Bearer editor-secret")

        revision = self.roster(bob).json()["config_revision"]
        demote_self = self.mutate("role", "alice", "editor", revision, headers=bob)
        self.assertEqual(200, demote_self.status_code, demote_self.text)
        self.assertEqual(403, self.roster(self.owner).status_code)

        revision = self.roster(bob).json()["config_revision"]
        restore_owner = self.mutate("role", "alice", "owner", revision, headers=bob)
        self.assertEqual(200, restore_owner.status_code, restore_owner.text)
        revision = self.roster().json()["config_revision"]
        remove_self = self.mutate("remove", "alice", revision=revision)
        self.assertEqual(200, remove_self.status_code, remove_self.text)
        denied = self.client.get("/api/remote/v1/snapshot", headers=self.owner)
        self.assertEqual("WORKSPACE_ACCESS_DENIED", denied.json()["error"])
        with open(self.path, encoding="utf-8") as handle:
            self.assertEqual(original_items, handle.read())

    def test_unknown_principal_last_owner_and_stale_revision_fail_without_write(self):
        revision = self.roster().json()["config_revision"]
        unknown = self.mutate("add", "unknown", "editor", revision)
        self.assertEqual("WORKSPACE_PRINCIPAL_UNKNOWN", unknown.json()["error"])
        last_owner = self.mutate("role", "alice", "viewer", revision=revision)
        self.assertEqual("WORKSPACE_LAST_OWNER_REQUIRED", last_owner.json()["error"])

        current = load_config(self.config_path)
        current["web"] = {"port": 12345}
        write_config(
            self.config_path,
            current,
            expected_revision=revision,
            require_revision=True,
        )
        stale = self.mutate("add", "dave", "viewer", revision)
        self.assertEqual("WORKSPACE_CONFIG_REVISION_CONFLICT", stale.json()["error"])
        self.assertNotEqual(revision, config_revision(self.config_path))
        updated = load_config(self.config_path)
        self.assertEqual(
            "editor",
            updated["workspaces"]["team"]["collaboration"]["members"]["bob"]["role"],
        )

    def test_mutation_audit_is_bounded_and_contains_no_credentials_or_config(self):
        revision = self.roster().json()["config_revision"]
        result = self.mutate("add", "dave", "editor", revision)
        self.assertEqual(200, result.status_code)
        with open(self.audit_path, encoding="utf-8") as handle:
            audit = handle.read()
        self.assertIn('"action":"member.add"', audit)
        self.assertIn('"principal":"alice"', audit)
        self.assertIn('"target_principal":"dave"', audit)
        self.assertNotIn("owner-secret", audit)
        self.assertNotIn(self.temp.name, audit)
        self.assertNotIn('"token_env"', audit)


if __name__ == "__main__":
    unittest.main()
