import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


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

    def test_summary_uses_the_stats_date_rule_for_all_breakdowns(self):
        Path(self.path).write_text(
            "[x] T Finished due:2026-04-01 done:2026-06-10 project:work\n"
            "[ ] T Scheduled do:2026-06-11 project:home\n"
            "[ ] T Undated project:work\n"
            "[x] T Old due:2026-06-10 done:2026-04-01 project:work\n"
            "[N] J Journal on:2026-06-11\n"
            "[x] H Later done:2026-07-11\n",
            encoding="utf-8",
        )
        route = "/api/stats/summary"
        response = self.client.get(
            route, params={"from": "2026-06-10", "to": "2026-06-11"}
        )
        self.assertEqual(200, response.status_code)
        result = response.json()
        self.assertEqual({"from": "2026-06-10", "to": "2026-06-11"}, result["range"])
        self.assertEqual(4, result["total"])
        self.assertEqual({"T": 3, "J": 1}, result["by_type"])
        self.assertEqual({"[x]": 1, "[ ]": 2, "[N]": 1}, result["by_status"])
        projects = {
            row["project"]: (row["done"], row["total"]) for row in result["by_project"]
        }
        self.assertEqual({"work": (1, 2), "home": (0, 1)}, projects)

        # Existing project filtering only narrows the project breakdown.
        project = self.client.get(
            route, params={"to": "2026-06-11", "project": "work"}
        ).json()
        self.assertEqual(4, project["total"])
        self.assertEqual(result["by_type"], project["by_type"])
        self.assertEqual(["work"], [row["project"] for row in project["by_project"]])
        self.assertEqual(2, project["by_project"][0]["total"])

        with patch("lifetxt.stats.timezone_today", return_value=date(2026, 6, 11)):
            from_only = self.client.get(route, params={"from": "2026-06-10"})
        self.assertEqual(200, from_only.status_code)
        self.assertEqual(result, from_only.json())

        # The date-less request still powers the Dashboard and All control.
        full = self.client.get(route).json()
        self.assertEqual(6, full["total"])
        self.assertEqual({"T": 4, "J": 1, "H": 1}, full["by_type"])
        self.assertEqual({"[x]": 3, "[ ]": 2, "[N]": 1}, full["by_status"])

    def test_common_period_clips_week_and_month_buckets_and_all_chart_sources(self):
        Path(self.path).write_text(
            "[x] T Before done:2024-01-28 elapsed:1m\n"
            "[x] T Start done:2024-01-29 elapsed:2m\n"
            "[x] T End done:2024-02-02 elapsed:3m\n"
            "[x] T After done:2024-02-03 elapsed:4m\n"
            "[ ] H Exercise done:2024-01-28 done:2024-01-29 done:2024-02-02 done:2024-02-03\n"
            "[N] J Mood on:2024-01-29 mood:good\n"
            "[N] J Later on:2024-02-03 mood:bad\n",
            encoding="utf-8",
        )
        period = {"from": "2024-01-29", "to": "2024-02-02"}
        for group, labels, counts in (
            (
                "daily",
                ["2024-01-29", "2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02"],
                [1, 0, 0, 0, 1],
            ),
            ("weekly", ["2024-01-29/2024-02-02"], [2]),
            ("monthly", ["2024-01-29/2024-01-31", "2024-02-01/2024-02-02"], [1, 1]),
        ):
            for chart in ("tasks", "habits", "mood"):
                with self.subTest(group=group, chart=chart):
                    result = self.client.get(
                        "/api/chart/" + chart, params={**period, "group": group}
                    ).json()
                    self.assertEqual({**period, "group": group}, result["range"])
                    self.assertEqual(labels, result["labels"])
                    if chart != "mood":
                        self.assertEqual(counts, result["datasets"][0]["data"])
                    else:
                        self.assertEqual({"good": 1}, result["counts"])
        elapsed = self.client.get("/api/chart/elapsed", params=period).json()
        self.assertEqual(period, elapsed["range"])
        self.assertEqual([5], elapsed["datasets"][0]["data"])
        heatmap = self.client.get("/api/chart/habits-heatmap", params=period).json()
        self.assertEqual(period, heatmap["range"])
        self.assertEqual(
            {"2024-01-29": 1, "2024-02-02": 1}, heatmap["habits"][0]["dates"]
        )
        summary = self.client.get("/api/stats/summary", params=period).json()
        self.assertEqual(period, summary["range"])
        self.assertEqual(2, summary["by_type"]["T"])

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
