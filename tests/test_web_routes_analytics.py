import os
import tempfile
import unittest
from pathlib import Path


try:
    from fastapi.testclient import TestClient
except Exception:
    TestClient = None


@unittest.skipIf(TestClient is None, "web extras unavailable")
class AnalyticsRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "life.txt")
        Path(self.path).write_text(
            "[x] T Finished done:2026-06-10 project:work elapsed:30m\n"
            "[ ] T Open project:work\n"
            "[x] H Exercise done:2026-06-10\n"
            "[N] J Journal on:2026-06-10 mood:good\n",
            encoding="utf-8",
        )
        from lifetxt.webapp import create_app

        self.client = TestClient(create_app([self.path], writable_path=self.path))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_analytics_routes_keep_paths_and_get_methods(self):
        routes = {
            (route.path, method)
            for route in self.client.app.routes
            for method in getattr(route, "methods", set())
        }
        expected = {
            ("/api/chart/tasks", "GET"),
            ("/api/chart/habits", "GET"),
            ("/api/chart/mood", "GET"),
            ("/api/chart/elapsed", "GET"),
            ("/api/chart/habits-heatmap", "GET"),
            ("/api/stats/summary", "GET"),
        }
        self.assertTrue(expected.issubset(routes))

    def test_analytics_payloads_keep_representative_shapes(self):
        query = "?from=2026-06-10&to=2026-06-10"
        responses = {
            path: self.client.get(path + query)
            for path in (
                "/api/chart/tasks",
                "/api/chart/habits",
                "/api/chart/mood",
                "/api/chart/elapsed",
                "/api/chart/habits-heatmap",
                "/api/stats/summary",
            )
        }
        self.assertTrue(
            all(response.status_code == 200 for response in responses.values())
        )
        self.assertEqual(
            {"labels", "datasets", "range"}, set(responses["/api/chart/tasks"].json())
        )
        self.assertEqual(
            {"labels", "datasets", "range"}, set(responses["/api/chart/habits"].json())
        )
        self.assertEqual(
            {"labels", "datasets", "mood_scale", "counts", "range"},
            set(responses["/api/chart/mood"].json()),
        )
        self.assertEqual(
            {"labels", "datasets", "range"}, set(responses["/api/chart/elapsed"].json())
        )
        self.assertEqual(
            {"habits", "range"}, set(responses["/api/chart/habits-heatmap"].json())
        )
        self.assertEqual(
            {"total", "by_type", "by_status", "by_project", "range"},
            set(responses["/api/stats/summary"].json()),
        )

    def test_read_only_and_bearer_auth_still_apply_to_analytics_routes(self):
        from lifetxt.webapp import create_app

        read_only = TestClient(
            create_app([self.path], writable_path=self.path, read_only=True)
        )
        self.assertEqual(200, read_only.get("/api/chart/tasks").status_code)

        protected = TestClient(
            create_app(
                [self.path],
                writable_path=self.path,
                config={"api": {"token": "test-token"}},
            )
        )
        self.assertEqual(401, protected.get("/api/chart/tasks").status_code)
        self.assertEqual(
            200,
            protected.get(
                "/api/chart/tasks", headers={"Authorization": "Bearer test-token"}
            ).status_code,
        )


if __name__ == "__main__":
    unittest.main()
