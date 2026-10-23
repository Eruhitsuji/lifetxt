"""Route, API compatibility and distribution contract for the State page."""

import tempfile
import unittest
from pathlib import Path
from importlib import resources

from lifetxt import webapp
from lifetxt.web_assets import STATE_HTML_PAGE

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


class StateAssetTests(unittest.TestCase):
    def test_page_assembles_all_packaged_assets_without_external_dependencies(self):
        self.assertTrue(STATE_HTML_PAGE.startswith("<!doctype html>"))
        self.assertNotIn("__STATE_", STATE_HTML_PAGE)
        for name in ("web_state.html", "web_state.css", "web_state.js"):
            self.assertTrue(resources.files("lifetxt").joinpath(name).read_bytes())
            self.assertIn(
                '"' + name + '"',
                (Path(__file__).parents[1] / "pyproject.toml").read_text(),
            )
        self.assertNotIn("<script src=", STATE_HTML_PAGE)
        self.assertNotIn('rel="manifest"', STATE_HTML_PAGE)


@unittest.skipIf(TestClient is None, "Web extras unavailable")
class StateRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "life.txt"
        self.path.write_text(
            "[/] S Other from:2026-01-01T08:00 state:meeting person:aaa id:other\n"
            "[/] S Self from:2026-01-01T09:00 state:busy person:self id:self\n"
        )

    def client(self, **kwargs):
        client = TestClient(
            webapp.create_app([str(self.path)], writable_path=str(self.path), **kwargs)
        )
        self.addCleanup(client.close)
        return client

    def test_direct_route_preserves_other_pages_and_no_store(self):
        client = self.client()
        page = client.get("/state")
        self.assertEqual(200, page.status_code)
        self.assertEqual("no-store", page.headers["Cache-Control"])
        self.assertIn('id="primary-states"', page.text)
        self.assertIn('id="status-form"', page.text)
        self.assertIn('id="end"', page.text)
        for route in ("/", "/capture", "/planner"):
            response = client.get(route)
            self.assertEqual(200, response.status_code, route)
            self.assertEqual("no-store", response.headers["Cache-Control"])
        self.assertNotIn('href="/state"', client.get("/").text)

    def test_route_keeps_existing_authentication(self):
        client = self.client(config={"api": {"token": "state-test-token"}})
        self.assertEqual(401, client.get("/state").status_code)
        response = client.get(
            "/state", headers={"Authorization": "Bearer state-test-token"}
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["Cache-Control"])

    def test_readonly_can_view_state_and_cannot_write(self):
        client = self.client(read_only=True)
        before = self.path.read_bytes()
        self.assertEqual(200, client.get("/state").status_code)
        self.assertTrue(client.get("/api/health").json()["read_only"])
        self.assertEqual(
            403, client.post("/api/status", json={"state": "focus"}).status_code
        )
        self.assertEqual(before, self.path.read_bytes())

    def test_existing_self_status_config_and_revision_contract(self):
        original = self.path.read_text()
        for mode in ("observe", "required"):
            with self.subTest(mode=mode):
                self.path.write_text(original)
                client = self.client(
                    config={
                        "web": {
                            "revision_mode": mode,
                            "presence": {
                                "states": {
                                    "commuting": "focus",
                                    "custom": "p-away",
                                    "bad": 'x" onclick=evil',
                                }
                            },
                        }
                    }
                )
                config = client.get("/api/config").json()
                self.assertEqual(9, len(config["status_states"]))
                self.assertEqual(
                    {"commuting": "p-focus", "custom": "p-away"},
                    config["web"]["presence"],
                )
                current = client.get("/api/status?person=self&active=true")
                self.assertEqual(
                    ["self"], [r["person"] for r in current.json()["records"]]
                )
                saved = client.post(
                    "/api/status",
                    json={"state": "focus", "title": "Deep work", "note": "Remember"},
                    headers={"If-Match": current.headers["ETag"]},
                )
                self.assertEqual(201, saved.status_code, saved.text)
                self.assertNotIn("X-Lifetxt-Legacy-Revision-Fallback", saved.headers)
                repeated = client.post(
                    "/api/status",
                    json={"state": "focus"},
                    headers={"If-Match": saved.headers["ETag"]},
                )
                self.assertEqual("focus", repeated.json()["unchanged"])
                ended = client.post(
                    "/api/status",
                    json={"end": True},
                    headers={"If-Match": repeated.headers["ETag"]},
                )
                self.assertEqual(201, ended.status_code)
                self.assertEqual(
                    [],
                    client.get("/api/status?person=self&active=true").json()["records"],
                )
                latest = client.get("/api/status?person=self&active=false").json()[
                    "records"
                ]
                self.assertFalse(latest[0]["active"])
                self.assertEqual("Deep work", latest[0]["title"])
                self.assertEqual(["Remember"], latest[0]["details"]["note"])
                self.assertIn("person:aaa", self.path.read_text())


if __name__ == "__main__":
    unittest.main()
