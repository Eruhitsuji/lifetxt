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
        self.assertEqual(1, lifecycle_analytics(timeline, "schedule")["earlier_count"])
        self.assertEqual(-1, lifecycle_analytics(timeline, "schedule")["net_shift_days"])
        self.assertEqual(0, lifecycle_analytics(timeline, "relation")["target_net"][0]["net"])
        self.assertEqual(1, len(lifecycle_analytics(timeline, "progress")["largest_deltas"]))

    def test_oscillation_is_two_contiguous_reverse_transitions(self):
        timeline = {"target_id": "T-1", "complete": True, "limitations": [], "diagnostics": [], "events": [
            {"record_id": "a", "event": "status_changed", "at": "2026-09-01T00:00:00Z", "valid": True, "payload": {"before_status": ["A"], "after_status": ["B"]}},
            {"record_id": "b", "event": "status_changed", "at": "2026-09-01T01:00:00Z", "valid": True, "payload": {"before_status": ["B"], "after_status": ["A"]}},
        ]}
        result = lifecycle_analytics(timeline, "oscillation")
        self.assertEqual(1, result["oscillation_count"])
        self.assertEqual(["a", "b"], result["oscillations"][0]["event_ids"])

    def test_workspace_stats_contains_global_counts_and_bounded_distribution(self):
        items = _items() + parse_text("[x] T Other id:T-2\n")[0]
        result = workspace_lifecycle_stats(items, duration=True)
        self.assertEqual(2, result["scanned_item_count"])
        self.assertIn("total_valid_event_count", result)
        self.assertEqual(1, result["duration_distribution"]["eligible_count"])
        self.assertIn("example_item_ids", result["duration_distribution"])
        self.assertEqual(2, len(result["coverage"]))
        self.assertIn("item", result["coverage_by_domain"])

    def test_window_comparison_includes_event_type_deltas(self):
        first = {"target_id": "T-1", "complete": True, "limitations": [], "events": [{"event": "created", "record_id": "a", "at": "2026-09-01T00:00:00Z", "valid": True}], "diagnostics": []}
        second = {"target_id": "T-1", "complete": True, "limitations": [], "events": [{"event": "created", "record_id": "a", "at": "2026-09-01T00:00:00Z", "valid": True}, {"event": "completed", "record_id": "b", "at": "2026-09-02T00:00:00Z", "valid": True}], "diagnostics": []}
        result = __import__("lifetxt.lifecycle_analytics", fromlist=["compare_lifecycle_windows"]).compare_lifecycle_windows(first, second)
        self.assertEqual(1, result["event_type_deltas"]["completed"])

    def test_schedule_lead_time_distinguishes_unknown_from_no_observation(self):
        timeline = {"target_id": "T-1", "complete": False, "limitations": ["history_partial"], "diagnostics": [], "events": [{"event": "completed", "record_id": "c", "at": "2026-09-02T00:00:00Z", "valid": True}]}
        self.assertEqual("unknown", lifecycle_analytics(timeline, "schedule_lead_time")["schedule_change_state"])

    def test_relation_round_trips_are_sequence_pairs_and_partial_net_is_unknown(self):
        rows = []
        for index, event in enumerate(("relation_added", "relation_removed", "relation_added", "relation_removed"), 1):
            rows.append({"record_id": str(index), "event": event, "at": "2026-09-01T%02d:00:00Z" % index, "sequence": index, "valid": True, "payload": {"relation": ["blocks"], "target": ["T-2"]}})
        complete = lifecycle_analytics({"target_id": "T-1", "complete": True, "limitations": [], "diagnostics": [], "events": rows}, "relation")
        self.assertEqual(2, complete["round_trip_count"])
        self.assertEqual(4, complete["target_net"][0]["change_count"])
        partial = lifecycle_analytics({"target_id": "T-1", "complete": False, "limitations": ["history_incomplete"], "diagnostics": [], "events": rows}, "relation")
        self.assertIsNone(partial["target_net"][0]["net"])
        self.assertFalse(partial["net_available"])

    def test_due_date_uses_workspace_calendar_date(self):
        timeline = {"target_id": "T-1", "complete": True, "limitations": [], "diagnostics": [], "events": [
            {"record_id": "s", "event": "schedule_changed", "at": "2026-09-01T12:00:00Z", "valid": True, "payload": {"field": ["due"], "after": ["2026-09-02"]}},
            {"record_id": "c", "event": "completed", "at": "2026-09-01T15:30:00Z", "valid": True, "payload": {"before_status": ["[/]"], "after_status": ["[x]"]}},
        ]}
        self.assertEqual("at_due", lifecycle_analytics(timeline, "due_variance", timezone_name="Asia/Tokyo")["classification"])

    def test_gap_does_not_create_oscillation(self):
        timeline = {"target_id": "T-1", "complete": True, "limitations": ["item_history_incomplete"], "diagnostics": [], "events": [
            {"record_id": "a", "event": "status_changed", "at": "2026-09-01T00:00:00Z", "sequence": 1, "valid": True, "payload": {"before_status": ["A"], "after_status": ["B"]}},
            {"record_id": "b", "event": "status_changed", "at": "2026-09-01T02:00:00Z", "sequence": 3, "valid": True, "payload": {"before_status": ["B"], "after_status": ["A"]}},
        ]}
        self.assertEqual(0, lifecycle_analytics(timeline, "oscillation")["oscillation_count"])

    def test_incomplete_status_dwell_is_unknown_not_authoritative(self):
        timeline = {"target_id": "T-1", "complete": False, "limitations": ["item_history_incomplete"], "diagnostics": [], "events": [
            {"event": "created", "at": "2026-09-01T00:00:00Z", "sequence": 1, "valid": True, "payload": {"after_status": ["[ ]"]}},
            {"event": "status_changed", "at": "2026-09-01T02:00:00Z", "sequence": 3, "valid": True, "payload": {"after_status": ["[/]"]}},
        ]}
        result = lifecycle_analytics(timeline, "status_dwell")
        self.assertEqual({}, dict(result["dwell_seconds"]))
        self.assertGreater(result["unknown_dwell_seconds"], 0)

    def test_schedule_datetime_shift_is_field_scoped(self):
        timeline = {"target_id": "T-1", "complete": True, "limitations": [], "diagnostics": [], "events": [
            {"event": "schedule_changed", "at": "2026-09-01T00:00:00Z", "valid": True, "payload": {"field": ["due"], "before": ["2026-09-01T10:00:00Z"], "after": ["2026-09-01T12:00:00Z"]}},
            {"event": "schedule_changed", "at": "2026-09-02T00:00:00Z", "valid": True, "payload": {"field": ["on"], "before": ["2026-09-02"], "after": ["2026-09-01"]}},
        ]}
        result = lifecycle_analytics(timeline, "schedule")
        self.assertEqual(7200, result["field_shifts"]["due"]["net_shift_seconds"])
        self.assertEqual(-1, result["field_shifts"]["on"]["net_shift_days"])
        self.assertEqual("2026-09-01T00:00:00Z", result["field_shifts"]["due"]["first_change"]["at"])

    def test_progress_partial_history_hides_rate_and_keeps_both_extremes(self):
        events = []
        for index, percent in enumerate((10, 40, 20), 1):
            events.append({"record_kind": "progress_event", "event": "progress_set", "at": "2026-09-%02dT00:00:00Z" % index, "sequence": index, "valid": True, "payload": {"after_progress": ["%d%%" % percent]}})
        result = lifecycle_analytics({"target_id": "T-1", "complete": False, "limitations": ["item_history_incomplete"], "diagnostics": [], "events": events}, "progress")
        self.assertIsNone(result["rate_per_day"])
        self.assertEqual(30, result["largest_positive_delta"]["delta"])
        self.assertEqual(-20, result["largest_negative_delta"]["delta"])

    def test_partial_due_and_provenance_preserve_uncertainty_and_identity(self):
        timeline = {"target_id": "T-1", "complete": False, "limitations": ["item_history_incomplete"], "diagnostics": [], "events": [
            {"record_id": "s", "event": "schedule_changed", "at": "2026-09-01T00:00:00Z", "valid": True, "payload": {"field": ["due"], "after": ["2026-09-02"]}},
            {"record_id": "c", "event": "completed", "at": "2026-09-02T00:00:00Z", "valid": True, "payload": {"actor": ["alice"], "source": ["import"]}},
        ]}
        due = lifecycle_analytics(timeline, "due_variance")
        provenance = lifecycle_analytics(timeline, "provenance")
        self.assertEqual("unavailable", due["classification"])
        self.assertEqual("due", due["affected_field"])
        self.assertEqual("actor", provenance["actor_first_last"]["alice"]["field"])
        self.assertEqual("c", provenance["provenance_evidence"][0]["record_id"])

    def test_workspace_limit_must_be_positive(self):
        with self.assertRaises(ValueError):
            workspace_lifecycle_stats(_items(), limit=0)


if __name__ == "__main__":
    unittest.main()
