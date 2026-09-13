"""Bounded change feed built from the existing Workspace Life Timeline."""

from .native_timeline import MAX_LIMIT
from .workspace_timeline import workspace_timeline

MEANINGFUL_EVENTS = frozenset(
    (
        "status_changed",
        "completed",
        "reopened",
        "canceled",
        "schedule_changed",
        "relation_added",
        "relation_removed",
        "progress_logged",
        "time_logged",
    )
)


def temporal_change_feed(
    items, since, until=None, limit=100, project=None, id_key="id"
):
    result = workspace_timeline(
        items, since=since, until=until, limit=MAX_LIMIT, project=project, id_key=id_key
    )
    changes = [
        event for event in result["events"] if event.get("event") in MEANINGFUL_EVENTS
    ]
    total_changes = len(changes)
    changes = changes[: int(limit)]
    result["schema"] = "temporal-change-feed-v1"
    result["events"] = changes
    result["bounds"]["returned_events"] = len(changes)
    result["bounds"]["limit"] = int(limit)
    result["bounds"]["truncated"] = total_changes > len(changes)
    return result
