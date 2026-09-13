"""Bounded change feed built from the existing Workspace Life Timeline."""

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
        items, since=since, until=until, limit=limit, project=project, id_key=id_key
    )
    changes = [
        event for event in result["events"] if event.get("event") in MEANINGFUL_EVENTS
    ]
    result["schema"] = "temporal-change-feed-v1"
    result["events"] = changes
    result["bounds"]["returned_events"] = len(changes)
    return result
