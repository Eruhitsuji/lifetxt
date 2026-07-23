import json
import os
import tempfile
import unittest

from lifetxt.mutation import MISSING_HASH
from lifetxt.revision_telemetry import RevisionMetricsStore, RevisionTelemetryError


class RevisionTelemetryRelocationV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = os.path.join(self.temp.name, "old", "metrics.json")
        self.destination = os.path.join(self.temp.name, "new", "metrics.json")
        self.store = RevisionMetricsStore(self.source, window_days=7)
        self.store.ensure()
        self.store.record_legacy_fallback("/api/timer")

    def test_relocation_preserves_observation_identity_and_counts(self):
        before = self.store.snapshot()
        result = self.store.relocate(self.destination, self.store.content_hash())
        after = RevisionMetricsStore(self.destination, window_days=7).snapshot()
        self.assertTrue(result["relocated"])
        self.assertEqual(before["server_instance_id"], after["server_instance_id"])
        self.assertEqual(before["observation_started_at"], after["observation_started_at"])
        self.assertEqual(1, after["legacy_fallback_total"])
        self.assertTrue(os.path.exists(self.source))

    def test_relocation_can_delete_source_with_recovery_journal(self):
        result = self.store.relocate(
            self.destination, self.store.content_hash(), delete_source=True
        )
        self.assertFalse(os.path.exists(self.source))
        self.assertTrue(os.path.exists(self.destination))
        self.assertTrue(result["transaction_id"])
        self.assertTrue(os.path.exists(result["journal_path"]))

    def test_relocation_refuses_stale_revision(self):
        stale = self.store.content_hash()
        self.store.record_legacy_fallback("/api/items")
        with self.assertRaises(Exception):
            self.store.relocate(self.destination, stale)
        self.assertFalse(os.path.exists(self.destination))

    def test_evidence_export_has_revision_and_no_metrics_path(self):
        output = os.path.join(self.temp.name, "evidence.json")
        report = self.store.export_evidence(output)
        self.assertNotEqual(MISSING_HASH, report["metrics_revision"])
        with open(output, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertNotIn("metrics_path", data)
        self.assertEqual(1, data["legacy_fallback_total"])

    def test_relocation_requires_existing_source_and_revision(self):
        missing = RevisionMetricsStore(os.path.join(self.temp.name, "missing.json"))
        with self.assertRaises(RevisionTelemetryError):
            missing.relocate(self.destination, MISSING_HASH)
        with self.assertRaises(RevisionTelemetryError):
            self.store.relocate(self.destination, None)


if __name__ == "__main__":
    unittest.main()
