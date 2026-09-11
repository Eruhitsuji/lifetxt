"""Deterministic, read-only analytics over the Native Timeline result."""

from __future__ import annotations

from collections import Counter, OrderedDict
import datetime

from .timeutil import parse_iso_datetime


def _instant(value):
    parsed = parse_iso_datetime(str(value or ""))
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(datetime.timezone.utc)


def _payload(row, key, default=None):
    values = (row.get("payload") or {}).get(key) or []
    return str(values[0]) if values else default


def _valid_rows(timeline):
    # native_timeline already filters invalid records.  Keep this guard so the
    # helper remains safe when called with a saved/externally supplied result.
    return [row for row in timeline.get("events", []) if row.get("valid", True)]


def _base(timeline, rows):
    types = Counter(str(row.get("event", "")) for row in rows)
    times = sorted(((_instant(row.get("at")), row) for row in rows if _instant(row.get("at"))), key=lambda pair: (pair[0], pair[1].get("record_id", "")))
    return OrderedDict((
        ("analysis_schema", "lifecycle-analytics-v1"),
        ("target_id", timeline.get("target_id")),
        ("observed_event_count", len(rows)),
        ("event_counts", OrderedDict((key, types[key]) for key in sorted(types))),
        ("first_event_at", times[0][0].isoformat().replace("+00:00", "Z") if times else None),
        ("last_event_at", times[-1][0].isoformat().replace("+00:00", "Z") if times else None),
        ("status_transition_count", sum(row.get("event") in ("status_changed", "completed", "reopened", "canceled") for row in rows)),
        ("schedule_change_count", sum(row.get("event") == "schedule_changed" for row in rows)),
        ("relation_change_count", sum(row.get("event") in ("relation_added", "relation_removed") for row in rows)),
        ("completed_count", sum(row.get("event") == "completed" for row in rows)),
        ("reopened_count", sum(row.get("event") == "reopened" for row in rows)),
        ("complete", bool(timeline.get("complete"))),
        ("limitations", list(timeline.get("limitations", []))),
        ("diagnostics", list(timeline.get("diagnostics", []))),
    ))


def lifecycle_summary(timeline):
    """Aggregate only the filtered valid events; timeline limit is irrelevant."""
    rows = _valid_rows(timeline)
    result = _base(timeline, rows)
    result["analysis"] = "lifecycle_summary"
    return result


def lifecycle_analytics(timeline, analysis="summary"):
    """Dispatch the small first-slice analytics without a second reader."""
    result = lifecycle_summary(timeline)
    rows = _valid_rows(timeline)
    if analysis in (None, "summary"):
        return result
    if analysis == "duration":
        created = next((row for row in rows if row.get("event") == "created"), None)
        completed = next((row for row in rows if row.get("event") == "completed"), None)
        result["analysis"] = "created_to_completed_duration"
        result["created_at"] = created.get("at") if created else None
        result["first_completed_at"] = completed.get("at") if completed else None
        start, end = (_instant(created.get("at")) if created else None), (_instant(completed.get("at")) if completed else None)
        result["duration_seconds"] = (end - start).total_seconds() if start and end and end >= start else None
        result["completion_event_count"] = result["completed_count"]
        if not start: result["limitations"].append("created_evidence_unavailable")
        if not end: result["limitations"].append("completed_evidence_unavailable")
        return result
    if analysis == "transitions":
        pairs = Counter()
        sequence = []
        for row in rows:
            if row.get("event") not in ("status_changed", "completed", "reopened", "canceled"): continue
            before, after = _payload(row, "before_status"), _payload(row, "after_status")
            if before and after and before != after:
                pair = before + " -> " + after; pairs[pair] += 1; sequence.append((pair, row))
        result["analysis"] = "status_transition_matrix"
        result["transitions"] = OrderedDict((key, pairs[key]) for key in sorted(pairs))
        result["transition_events"] = [row.get("record_id") for _, row in sequence]
        return result
    if analysis == "completion_cycles":
        state, cycles, recoveries = None, 0, 0
        for row in rows:
            if row.get("event") == "completed": state = "completed"
            elif row.get("event") == "reopened":
                if state == "completed": cycles += 1
                state = "reopened"
            elif row.get("event") == "completed" and state == "reopened": recoveries += 1
        result["analysis"] = "completion_reopen_cycles"; result["cycle_count"] = cycles; result["recovery_count"] = recoveries
        result["first_completion_at"] = next((r.get("at") for r in rows if r.get("event") == "completed"), None)
        result["latest_completion_at"] = next((r.get("at") for r in reversed(rows) if r.get("event") == "completed"), None)
        result["latest_reopen_at"] = next((r.get("at") for r in reversed(rows) if r.get("event") == "reopened"), None)
        return result
    raise ValueError("Unknown lifecycle analytics %r." % analysis)
