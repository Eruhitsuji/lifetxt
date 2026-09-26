import os
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


@unittest.skipIf(TestClient is None, "web extras unavailable")
class PriorityMatrixRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        Path(self.path).write_text(
            "[ ] T First importance:high priority:C\n"
            "[/] T Second importance:low priority:A\n"
            "[ ] T Unclassified due:2026-09-26 priority:B\n"
            "[x] T Done importance:high\n"
            "[ ] E Event importance:high\n",
            encoding="utf-8",
        )
        from lifetxt.webapp import create_app

        self.client = TestClient(create_app([self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_matrix_route_returns_counts_and_priority_without_reordering(self):
        response = self.client.get("/api/priority-matrix")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload["counts"]), {"Q1", "Q2", "Q3", "Q4", "unclassified"})
        self.assertEqual(payload["counts"]["Q2"], 1)
        self.assertEqual(payload["counts"]["unclassified"], 1)
        self.assertEqual([row["title"] for row in payload["groups"]["Q2"]], ["First"])
        self.assertEqual(payload["groups"]["Q2"][0]["priority"], "C")
        self.assertNotIn("Done", [row["title"] for rows in payload["groups"].values() for row in rows])
        self.assertNotIn("Event", [row["title"] for rows in payload["groups"].values() for row in rows])
        self.assertTrue(payload["evaluated_at"])
        self.assertTrue(payload["timezone"])

    def test_matrix_route_respects_read_only_and_bearer_auth(self):
        from lifetxt.webapp import create_app

        readonly = TestClient(create_app([self.path], writable_path=self.path, read_only=True))
        self.assertEqual(200, readonly.get("/api/priority-matrix").status_code)
        protected = TestClient(create_app([self.path], writable_path=self.path, config={"api": {"token": "secret"}}))
        self.assertEqual(401, protected.get("/api/priority-matrix").status_code)
        self.assertEqual(200, protected.get("/api/priority-matrix", headers={"Authorization": "Bearer secret"}).status_code)


if __name__ == "__main__":
    unittest.main()
