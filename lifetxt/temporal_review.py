"""Deterministic retrospective projection over the workspace Life Timeline."""

from collections import OrderedDict
import datetime

from .review import resolve_review_range
from .agenda import agenda_records
from .timeutil import parse_date_or_datetime
from .workspace_timeline import workspace_timeline


def _date_bound(value, end=False):
    parsed = datetime.date.fromisoformat(value)
    clock = datetime.time.max if end else datetime.time.min
    return datetime.datetime.combine(
        parsed, clock, tzinfo=datetime.timezone.utc
    ).isoformat()


def build_temporal_review(
    items, since=None, until=None, week=False, limit=100, project=None, id_key="id"
):
    if week and (since or until):
        raise ValueError("--week cannot be combined with --since/--until.")
    if week:
        start, end = resolve_review_range(week=True)
        since, until = (
            _date_bound(start.isoformat()),
            _date_bound(end.isoformat(), end=True),
        )
    if not since:
        raise ValueError("Temporal review requires --since, --until, or --week.")
    if "T" not in str(since):
        since = _date_bound(str(since))
    if until and "T" not in str(until):
        until = _date_bound(str(until), end=True)
    result = workspace_timeline(
        items, id_key=id_key, limit=limit, since=since, until=until, project=project
    )
    events = result["events"]
    by_event = OrderedDict()
    for row in events:
        by_event[row.get("event", "unknown")] = (
            by_event.get(row.get("event", "unknown"), 0) + 1
        )
    changed = [
        row for row in events if row.get("event") not in ("created", "completed")
    ]
    completed = [row for row in events if row.get("event") == "completed"]
    reopened = [
        row
        for row in events
        if row.get("event") in ("reopened", "canceled", "schedule_changed")
    ]
    upcoming = []
    if until:
        boundary = parse_date_or_datetime(until, is_end=True)
        for row in agenda_records(items, boundary, None):
            upcoming.append(
                OrderedDict(
                    (
                        ("id", row.get("source_id")),
                        ("title", row["title"]),
                        ("when", row["when"]),
                        ("field", row["key"]),
                    )
                )
            )
    carry_forward = []
    for item in items:
        if item.kind == "T" and item.status in ("[ ]", "[/]", "[>]", "[?]"):
            if project and project not in [
                str(v) for v in item.details.get("project", [])
            ]:
                continue
            carry_forward.append(
                OrderedDict(
                    (
                        ("id", (item.details.get(id_key) or [""])[0]),
                        ("title", item.title),
                    )
                )
            )
    result = OrderedDict(
        (
            ("schema", "temporal-life-review-v1"),
            ("period", OrderedDict((("since", since), ("until", until)))),
            ("source", "workspace-life-timeline-v1"),
            ("complete", result["complete"]),
            ("limitations", result["limitations"]),
            ("diagnostics", result["diagnostics"]),
            ("bounds", result["bounds"]),
            (
                "counts",
                OrderedDict(
                    (
                        ("events", len(events)),
                        ("changed", len(changed)),
                        ("completed", len(completed)),
                        ("reopened_or_rescheduled", len(reopened)),
                        ("carry_forward", len(carry_forward)),
                    )
                ),
            ),
            ("event_counts", by_event),
            ("completed", completed),
            ("changed", changed),
            ("reopened_or_rescheduled", reopened),
            ("carry_forward", carry_forward),
            ("upcoming", upcoming[:limit]),
        )
    )
    return result
