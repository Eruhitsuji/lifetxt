import importlib.util
import os
import tempfile
import unittest

from lifetxt import webapp


@unittest.skipUnless(
    importlib.util.find_spec("fastapi") is not None
    and importlib.util.find_spec("httpx") is not None,
    "Web test dependencies are not installed.",
)
class RevisionMigrationMetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        with open(self.path, "w", encoding="utf-8", newline="") as handle:
            handle.write("[ ] T Existing id:T-1\n")
        from fastapi.testclient import TestClient
        self.client = TestClient(webapp.create_app(paths=[self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_legacy_write_is_counted_and_returns_machine_readable_headers(self):
        before = self.client.get("/api/revision-metrics")
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()["legacy_fallback_total"], 0)

        response = self.client.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Legacy", "details": {}},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers.get("deprecation"), "true")
        self.assertEqual(
            response.headers.get("x-lifetxt-legacy-revision-fallback"),
            "used",
        )
        self.assertIn("299 lifetxt", response.headers.get("warning", ""))

        metrics = self.client.get("/api/revision-metrics").json()
        self.assertEqual(metrics["legacy_fallback_total"], 1)
        self.assertEqual(metrics["legacy_fallback_by_path"]["/api/items"], 1)
        self.assertTrue(metrics["legacy_fallback_last_used"].endswith("Z"))

    def test_revision_aware_write_does_not_increment_legacy_counter(self):
        revision = self.client.get("/api/revision").headers["etag"]
        response = self.client.post(
            "/api/items",
            headers={"If-Match": revision},
            json={"status": "[ ]", "type": "T", "title": "Safe", "details": {}},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.headers.get("x-lifetxt-legacy-revision-fallback"))
        metrics = self.client.get("/api/revision-metrics").json()
        self.assertEqual(metrics["legacy_fallback_total"], 0)

    def test_strict_session_still_rejects_missing_revision(self):
        self.client.get("/api/revision")
        response = self.client.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Rejected", "details": {}},
        )
        self.assertEqual(response.status_code, 428)
        self.assertEqual(response.json()["error"], "PRECONDITION_REQUIRED")
        metrics = self.client.get("/api/revision-metrics").json()
        self.assertEqual(metrics["legacy_fallback_total"], 0)


if __name__ == "__main__":
    unittest.main()
