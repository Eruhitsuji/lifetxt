import datetime
import unittest

from lifetxt.historical_temporal import historical_snapshot, thread_from_snapshot
from lifetxt.temporal_diff import temporal_diff
from tests.test_historical_temporal import GitHistoryCase


TODAY = datetime.date(2026, 9, 9)


class TemporalDiffTests(GitHistoryCase):
    def _diff(self, before, after, target="target", **bounds):
        before_snapshot = historical_snapshot([self.life], before)
        after_snapshot = historical_snapshot([self.life], after)
        defaults = {
            "max_depth": 8,
            "max_nodes": 50,
            "window_days": 7,
            "temporal_limit": 20,
            "stale_after_days": 14,
        }
        defaults.update(bounds)
        before_thread = thread_from_snapshot(
            before_snapshot, target, TODAY, allow_missing_target=True, **defaults
        )
        after_thread = thread_from_snapshot(
            after_snapshot, target, TODAY, allow_missing_target=True, **defaults
        )
        return temporal_diff(
            before_thread,
            after_thread,
            before_snapshot["historical"],
            after_snapshot["historical"],
            target,
        )

    def test_reports_items_status_edges_and_resolved_consistency(self):
        before = self._commit(
            "[ ] E Old id:old on:2026-09-10\n"
            "[ ] E Target id:target due:2026-09-01 follows:old\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Old id:old on:2026-09-10\n"
            "[x] E Target id:target on:2026-09-11\n"
            "[ ] E Next id:next on:2026-09-12 follows:target\n",
            "2026-01-02T00:00:00+00:00",
        )
        result = self._diff(before, after)
        self.assertEqual(["next"], [item["id"] for item in result["items"]["added"]])
        self.assertEqual(["old"], [item["id"] for item in result["items"]["removed"]])
        self.assertEqual(
            "[x]", result["items"]["changed"][0]["changes"]["status"]["to"]
        )
        self.assertEqual("next", result["explicit"]["added_edges"][0]["source_id"])
        self.assertEqual("old", result["explicit"]["removed_edges"][0]["target_id"])
        self.assertEqual(
            "follows", result["consistency"]["resolved_warnings"][0]["relation"]
        )
        self.assertEqual([], result["consistency"]["introduced_warnings"])
        self.assertTrue(result["derived"]["added_edges"])
        self.assertTrue(result["derived"]["removed_facts"])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        from lifetxt.schema_extensions_v27 import temporal_diff_v1_schema

        self.assertEqual(
            [],
            list(Draft202012Validator(temporal_diff_v1_schema()).iter_errors(result)),
        )

    def test_introduced_consistency_uses_shared_warning_identity(self):
        before = self._commit(
            "[ ] E Old id:old on:2026-09-01\n"
            "[ ] E Target id:target on:2026-09-10 follows:old\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Old id:old on:2026-09-10\n"
            "[ ] E Target id:target on:2026-09-01 follows:old\n",
            "2026-01-02T00:00:00+00:00",
        )
        result = self._diff(before, after)
        self.assertEqual(
            "follows", result["consistency"]["introduced_warnings"][0]["relation"]
        )
        self.assertEqual([], result["consistency"]["resolved_warnings"])

    def test_target_missing_is_an_added_lifecycle_without_fallback(self):
        before = self._commit(
            "[ ] E Other id:other\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Target id:target\n",
            "2026-01-02T00:00:00+00:00",
        )
        result = self._diff(before, after)
        self.assertEqual({"from": False, "to": True}, dict(result["availability"]))
        self.assertEqual(["target"], [item["id"] for item in result["items"]["added"]])

    def test_serialization_order_only_change_is_a_noop(self):
        before = self._commit(
            "[ ] E Old id:old\n[ ] E Target id:target follows:old\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Target follows:old id:target\n[ ] E Old id:old\n",
            "2026-01-02T00:00:00+00:00",
        )
        result = self._diff(before, after)
        self.assertEqual([], result["items"]["added"])
        self.assertEqual([], result["items"]["removed"])
        self.assertEqual([], result["items"]["changed"])
        self.assertEqual([], result["explicit"]["added_edges"])
        self.assertEqual([], result["explicit"]["removed_edges"])
        self.assertTrue(result["complete"])

    def test_bounds_make_comparison_explicitly_incomplete(self):
        before = self._commit(
            "[ ] E Target id:target follows:a\n[ ] E A id:a follows:b\n[ ] E B id:b\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Target id:target follows:a\n[ ] E A id:a follows:b\n[ ] E B id:b\n",
            "2026-01-02T00:00:00+00:00",
        )
        result = self._diff(before, after, max_nodes=1)
        self.assertFalse(result["complete"])
        self.assertIn("from_thread_truncated", result["limitations"])
        self.assertIn("to_thread_truncated", result["limitations"])

    def test_partial_path_evidence_is_attributed_to_the_revision_side(self):
        before = self._commit(
            "[ ] E Target id:target\n",
            "2026-01-01T00:00:00+00:00",
        )
        after = self._commit(
            "[ ] E Target id:target\n",
            "2026-01-02T00:00:00+00:00",
            extra="[ ] E Extra id:extra follows:target\n",
        )
        before_snapshot = historical_snapshot([self.life, self.extra], before)
        after_snapshot = historical_snapshot([self.life, self.extra], after)
        bounds = {
            "max_depth": 8,
            "max_nodes": 50,
            "window_days": 7,
            "temporal_limit": 20,
            "stale_after_days": 14,
        }
        before_thread = thread_from_snapshot(before_snapshot, "target", TODAY, **bounds)
        after_thread = thread_from_snapshot(after_snapshot, "target", TODAY, **bounds)
        result = temporal_diff(
            before_thread,
            after_thread,
            before_snapshot["historical"],
            after_snapshot["historical"],
            "target",
        )
        self.assertFalse(result["complete"])
        self.assertIn("from:missing_at_revision:extra.life.txt", result["limitations"])
        self.assertIn("from_evidence_incomplete", result["limitations"])


if __name__ == "__main__":
    unittest.main()
