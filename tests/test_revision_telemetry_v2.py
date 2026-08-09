import datetime
import importlib.util
import json
import os
import tempfile
import unittest

from lifetxt.mutation import (
    MISSING_HASH,
    MutationConflict,
    read_text_snapshot,
    write_text,
)
from lifetxt.revision_telemetry import (
    RevisionMetricsStore,
    RevisionTelemetryError,
    initial_metrics,
    migration_window_days,
    revision_mode,
)


class RevisionTelemetryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "revision.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_persists_across_store_instances(self):
        first = RevisionMetricsStore(self.path, mode="observe", window_days=14)
        first.ensure()
        first.record_legacy_fallback("/api/items")
        second = RevisionMetricsStore(self.path, mode="observe", window_days=14)
        report = second.snapshot()
        self.assertEqual(1, report["legacy_fallback_total"])
        self.assertEqual(1, report["legacy_fallback_by_path"]["/api/items"])
        self.assertTrue(report["legacy_fallback_last_used"].endswith("Z"))

    def test_reset_requires_and_checks_exact_revision(self):
        store = RevisionMetricsStore(self.path)
        store.ensure()
        store.record_legacy_fallback("/api/items")
        expected = read_text_snapshot(self.path).content_hash
        store.reset(expected)
        self.assertEqual(0, store.snapshot()["legacy_fallback_total"])
        with self.assertRaises(MutationConflict):
            store.reset(expected)

    def test_reset_can_initialize_missing_store_with_missing_hash(self):
        store = RevisionMetricsStore(self.path)
        report = store.reset(MISSING_HASH)
        self.assertEqual(0, report["legacy_fallback_total"])
        self.assertTrue(os.path.exists(self.path))

    def test_readiness_requires_zero_usage_for_full_window(self):
        fixed = datetime.datetime(2026, 7, 23, tzinfo=datetime.timezone.utc)
        value = initial_metrics("observe", 14, now=fixed - datetime.timedelta(days=15))
        value["last_persisted_at"] = value["observation_started_at"]
        write_text(
            self.path,
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            expected_hash=MISSING_HASH,
            operation="test.metrics",
            create=True,
        )
        store = RevisionMetricsStore(self.path, mode="observe", window_days=14)
        report = store.snapshot(now=fixed)
        self.assertTrue(report["ready_to_require_revisions"])
        store.record_legacy_fallback("/api/items", now=fixed)
        self.assertFalse(store.snapshot(now=fixed)["ready_to_require_revisions"])

    def test_invalid_mode_and_window_are_rejected(self):
        with self.assertRaises(RevisionTelemetryError):
            revision_mode({"web": {"revision_mode": "unsafe"}})
        with self.assertRaises(RevisionTelemetryError):
            migration_window_days({"web": {"revision_migration_window_days": -1}})


@unittest.skipUnless(
    importlib.util.find_spec("fastapi") is not None
    and (
        importlib.util.find_spec("httpx2") is not None
        or importlib.util.find_spec("httpx") is not None
    ),
    "Web test dependencies are not installed.",
)
class RevisionTelemetryWebTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.life = os.path.join(self.temp_dir.name, "life.txt")
        self.metrics = os.path.join(self.temp_dir.name, "metrics.json")
        with open(self.life, "w", encoding="utf-8") as handle:
            handle.write("[ ] T Existing id:T-1\n")
        from fastapi.testclient import TestClient
        from lifetxt import webapp

        self.TestClient = TestClient
        self.webapp = webapp

    def tearDown(self):
        self.temp_dir.cleanup()

    def app(self, mode="observe"):
        return self.webapp.create_app(
            paths=[self.life],
            writable_path=self.life,
            config={
                "web": {
                    "revision_mode": mode,
                    "revision_metrics_path": self.metrics,
                    "revision_migration_window_days": 7,
                },
                "defaults": {"timezone": "Asia/Tokyo"},
            },
        )

    def test_observe_mode_persists_fallback_across_app_restart(self):
        first = self.TestClient(self.app("observe"))
        response = first.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Legacy", "details": {}},
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual("observe", response.headers["x-lifetxt-revision-mode"])
        second = self.TestClient(self.app("observe"))
        metrics = second.get("/api/revision-metrics").json()
        self.assertEqual(1, metrics["legacy_fallback_total"])
        self.assertEqual(1, metrics["legacy_fallback_by_path"]["/api/items"])
        self.assertEqual(self.metrics, metrics["metrics_path"])

    def test_required_mode_rejects_unconditional_write_before_inner_fallback(self):
        client = self.TestClient(self.app("required"))
        response = client.post(
            "/api/items",
            json={"status": "[ ]", "type": "T", "title": "Rejected", "details": {}},
        )
        self.assertEqual(428, response.status_code)
        self.assertEqual("required", response.json()["revision_mode"])
        self.assertEqual(
            0, client.get("/api/revision-metrics").json()["legacy_fallback_total"]
        )

    def test_required_mode_accepts_if_match_and_exposes_timezone(self):
        client = self.TestClient(self.app("required"))
        revision = client.get("/api/revision").headers["etag"]
        response = client.post(
            "/api/items",
            headers={"If-Match": revision},
            json={"status": "[ ]", "type": "T", "title": "Safe", "details": {}},
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual("Asia/Tokyo", response.headers["x-lifetxt-timezone"])
        self.assertEqual("required", response.headers["x-lifetxt-revision-mode"])

    def test_metrics_export_contains_metrics_revision(self):
        client = self.TestClient(self.app("observe"))
        response = client.get("/api/revision-metrics/export")
        self.assertEqual(200, response.status_code)
        self.assertRegex(response.json()["metrics_revision"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            response.json()["metrics_revision"],
            response.headers["x-lifetxt-metrics-revision"],
        )


if __name__ == "__main__":
    unittest.main()
