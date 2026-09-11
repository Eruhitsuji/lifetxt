import unittest

from lifetxt.lifecycle_analytics import lifecycle_analytics, lifecycle_summary, workspace_lifecycle_stats
from lifetxt.native_history import build_item_event
from lifetxt.native_timeline import native_timeline
from lifetxt.parser import parse_text
from lifetxt.serializer import item_to_line


REVISION = "a" * 64


def _items():
    events = [
        build_item_event("T-1", "created", "2026-09-01T00:00:00Z", 1, "TX-1", REVISION, item_kind="T", item_title="Task", after_status="[ ]"),
        build_item_event("T-1", "status_changed", "2026-09-01T01:00:00Z", 2, "TX-2", REVISION, before_status="[ ]", after_status="[/]"),
        build_item_event("T-1", "completed", "2026-09-01T02:00:00Z", 3, "TX-3", REVISION, before_status="[/]", after_status="[x]"),
    ]
    text = "[x] T Task id:T-1\n" + "\n".join(item_to_line(event) for event in events) + "\n"
    return parse_text(text)[0]


class LifecycleAnalyticsTests(unittest.TestCase):
    def test_summary_aggregate_is_independent_of_display_limit(self):
        items = _items()
        small = native_timeline(items, "T-1", limit=1, include_all_valid=True)
        large = native_timeline(items, "T-1", limit=100, include_all_valid=True)
        self.assertEqual(lifecycle_summary(small), lifecycle_summary(large))
        self.assertEqual(3, lifecycle_summary(small)["observed_event_count"])

    def test_duration_and_transition_projections_share_the_same_reader(self):
        timeline = native_timeline(_items(), "T-1", include_all_valid=True)
        duration = lifecycle_analytics(timeline, "duration")
        transitions = lifecycle_analytics(timeline, "transitions")
        self.assertEqual(7200, duration["duration_seconds"])
        self.assertEqual(1, transitions["transitions"]["[ ] -> [/]" ])
        self.assertEqual(1, transitions["transitions"]["[/] -> [x]"])

    def test_invalid_events_are_not_aggregated(self):
        timeline = native_timeline(_items(), "T-1", include_all_valid=True)
        timeline["_all_valid_events"].append({"event": "completed", "valid": False})
        self.assertEqual(3, lifecycle_summary(timeline)["observed_event_count"])

    def test_all_projection_names_are_deterministic_and_explainable(self):
        timeline = {
            "target_id": "T-1", "complete": True, "limitations": [], "diagnostics": [],
            "events": [
                {"record_kind": "item_event", "record_id": "1", "event": "created", "at": "2026-09-01T00:00:00Z", "valid": True, "payload": {"after_status": ["[ ]"], "actor": ["alice"]}},
                {"record_kind": "item_event", "record_id": "2", "event": "status_changed", "at": "2026-09-01T01:00:00+01:00", "valid": True, "payload": {"before_status": ["[ ]"], "after_status": ["[/]"], "actor": ["alice"]}},
                {"record_kind": "item_event", "record_id": "3", "event": "schedule_changed", "at": "2026-09-01T02:00:00Z", "valid": True, "payload": {"field": ["due"], "before": ["2026-09-05"], "after": ["2026-09-04"]}},
                {"record_kind": "item_event", "record_id": "4", "event": "relation_added", "at": "2026-09-01T03:00:00Z", "valid": True, "payload": {"relation": ["blocks"], "target": ["T-2"]}},
                {"record_kind": "item_event", "record_id": "5", "event": "relation_removed", "at": "2026-09-01T04:00:00Z", "valid": True, "payload": {"relation": ["blocks"], "target": ["T-2"]}},
                {"record_kind": "progress_event", "record_id": "6", "event": "progress_set", "at": "2026-09-01T05:00:00Z", "valid": True, "payload": {"after_progress": ["20%"]}},
                {"record_kind": "progress_event", "record_id": "7", "event": "progress_set", "at": "2026-09-02T05:00:00Z", "valid": True, "payload": {"after_progress": ["40%"]}},
                {"record_kind": "time_entry", "record_id": "8", "event": "time_entry", "at": "2026-09-02T06:00:00Z", "valid": True, "payload": {"elapsed": ["30m"], "activity": ["testing"], "on": ["2026-09-02"]}},
                {"record_kind": "item_event", "record_id": "9", "event": "completed", "at": "2026-09-04T00:00:00Z", "valid": True, "payload": {"before_status": ["[/]"], "after_status": ["[x]"]}},
            ],
        }
        for name in ("duration", "transitions", "status_dwell", "completion_cycles", "gaps", "cadence", "oscillation", "provenance", "schedule", "schedule_lead_time", "progress", "effort", "due_variance", "relation"):
            result = lifecycle_analytics(timeline, name)
            self.assertEqual("lifecycle-analytics-v1", result["analysis_schema"])
            self.assertIn("limitations", result)
        self.assertEqual("at_due", lifecycle_analytics(timeline, "due_variance")["classification"])
        self.assertEqual(20, lifecycle_analytics(timeline, "progress")["total_delta"])
        self.assertEqual(1800, lifecycle_analytics(timeline, "effort")["total_elapsed_seconds"])

    def test_workspace_stats_contains_global_counts_and_bounded_distribution(self):
        items = _items() + parse_text("[x] T Other id:T-2\n")[0]
        result = workspace_lifecycle_stats(items, duration=True)
        self.assertEqual(2, result["scanned_item_count"])
        self.assertIn("total_valid_event_count", result)
        self.assertEqual(1, result["duration_distribution"]["eligible_count"])
        self.assertIn("example_item_ids", result["duration_distribution"])
        self.assertEqual(2, len(result["coverage"]))


if __name__ == "__main__":
    unittest.main()
