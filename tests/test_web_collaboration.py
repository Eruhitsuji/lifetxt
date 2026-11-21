"""Ordinary Web collaboration through the production ASGI entry point."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lifetxt import bootstrap_legacy_surfaces

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


ORIGIN = "https://testserver"
BROWSER = "/api/web/v1/browser"


@unittest.skipIf(TestClient is None, "Web extras unavailable")
class WebCollaborationTests(unittest.TestCase):
    def setUp(self):
        bootstrap_legacy_surfaces()
        from lifetxt.webapp import create_app

        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.source = Path(folder) / "team.life.txt"
        self.source.write_text("", encoding="utf-8")
        self.members = {name: {"role": role} for name, role in (
            ("alice", "editor"), ("bob", "editor"), ("carol", "viewer")
        )}
        users = ("alice", "bob", "carol", "outsider")
        env = {f"LIFETXT_WEB_TEST_{name.upper()}": f"fixture-{name}" for name in users}
        self.enterContext(patch.dict(os.environ, env))
        config = {
            "web": {"revision_mode": "required"},
            "default_workspace": "team",
            "workspaces": {"team": {"collaboration": {"members": self.members}}},
            "remote": {
                "enabled": True,
                "principals": [
                    {
                        "id": name,
                        "role": "editor",
                        "token_env": f"LIFETXT_WEB_TEST_{name.upper()}",
                    }
                    for name in users
                ],
            },
        }
        path = str(self.source)
        self.app = create_app(paths=[path], writable_path=path, config=config)

    def client(self):
        client = TestClient(self.app, base_url=ORIGIN)
        self.addCleanup(client.close)
        return client

    def login(self, client, name):
        response = client.post(
            BROWSER + "/login", headers={"Origin": ORIGIN},
            json={"token": f"fixture-{name}"},
        )
        self.assertEqual(200, response.status_code, response.text)
        data = response.json()
        return {"Origin": ORIGIN, data["csrf_header"]: data["csrf_token"]}

    def test_member_startup_and_live_role_change(self):
        client = self.client()
        headers = self.login(client, "alice")
        config = client.get("/api/config")
        self.assertEqual(200, config.status_code, config.text)
        self.assertNotIn("paths", config.json())
        self.assertEqual(403, client.get("/api/backup/status").status_code)
        self.assertTrue(client.get("/api/health").json()["can_write"])
        self.members["alice"]["role"] = "viewer"
        self.assertTrue(client.get(BROWSER + "/session").json()["read_only"])
        self.assertFalse(client.get("/api/health").json()["can_write"])
        self.assertEqual(403, client.post("/api/items/raw", headers=headers, json={}).status_code)
        del self.members["alice"]
        self.assertEqual(403, client.get(BROWSER + "/session").status_code)

    def test_non_member_csrf_and_logout_revocation(self):
        client = self.client()
        rejected = client.post(
            BROWSER + "/login", headers={"Origin": ORIGIN},
            json={"token": "fixture-outsider"},
        )
        self.assertEqual(403, rejected.status_code)
        headers = self.login(client, "carol")
        self.assertEqual(403, client.post(BROWSER + "/logout", headers={"Origin": ORIGIN}).status_code)
        self.assertEqual(403, client.post(BROWSER + "/logout", headers={**headers, "Origin": "https://other.test"}).status_code)
        cookie = client.cookies.get("lifetxt_web_session")
        self.assertTrue(cookie)
        self.assertEqual(200, client.post(BROWSER + "/logout", headers=headers).status_code)
        self.assertEqual(401, client.get(BROWSER + "/session", headers={"Cookie": f"lifetxt_web_session={cookie}"}).status_code)

    def test_stale_edit_cannot_overwrite_accepted_write(self):
        first, second = self.client(), self.client()
        first_headers = self.login(first, "alice")
        second_headers = self.login(second, "bob")
        revision = first.get("/api/items").headers["ETag"]
        self.assertEqual(revision, second.get("/api/items").headers["ETag"])
        first_line = {"line": '[ ] T "First accepted write"'}
        response = first.post("/api/items/raw", headers=first_headers, json=first_line)
        self.assertEqual(428, response.status_code, response.text)
        response = first.post("/api/items/raw", headers={**first_headers, "If-Match": revision}, json=first_line)
        self.assertEqual(201, response.status_code, response.text)
        response = second.post(
            "/api/items/raw", headers={**second_headers, "If-Match": revision},
            json={"line": '[ ] T "Stale second write"'},
        )
        self.assertEqual(409, response.status_code, response.text)
        self.assertIn("First accepted write", self.source.read_text(encoding="utf-8"))
        self.assertNotIn("Stale second write", self.source.read_text(encoding="utf-8"))
