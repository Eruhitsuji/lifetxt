import unittest

from lifetxt.lifecycle_analytics import lifecycle_analytics, lifecycle_summary
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


if __name__ == "__main__":
    unittest.main()
