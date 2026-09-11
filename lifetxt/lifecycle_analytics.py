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
    if analysis == "status_dwell":
        intervals = Counter(); open_status = None; open_at = None
        for row in rows:
            if row.get("event") not in ("created", "status_changed", "completed", "reopened", "canceled"): continue
            before, after = _payload(row, "before_status"), _payload(row, "after_status")
            if row.get("event") == "created": after = after or ""
            current = _instant(row.get("at"))
            if open_status is not None and open_at and current and current >= open_at:
                intervals[open_status] += (current - open_at).total_seconds()
            if after: open_status, open_at = after, current
        result["analysis"] = "status_dwell"; result["dwell_seconds"] = OrderedDict((key, intervals[key]) for key in sorted(intervals)); result["open_interval"] = bool(open_status)
        if open_status: result["limitations"].append("open_status_interval")
        return result
    if analysis == "completion_cycles":
        state, cycles, recoveries = None, 0, 0
        for row in rows:
            if row.get("event") == "completed":
                if state == "reopened": recoveries += 1
                state = "completed"
            elif row.get("event") == "reopened":
                if state == "completed": cycles += 1
                state = "reopened"
        result["analysis"] = "completion_reopen_cycles"; result["cycle_count"] = cycles; result["recovery_count"] = recoveries
        result["first_completion_at"] = next((r.get("at") for r in rows if r.get("event") == "completed"), None)
        result["latest_completion_at"] = next((r.get("at") for r in reversed(rows) if r.get("event") == "completed"), None)
        result["latest_reopen_at"] = next((r.get("at") for r in reversed(rows) if r.get("event") == "reopened"), None)
        return result
    if analysis == "gaps":
        ordered = sorted(((value, row) for row in rows if (value := _instant(row.get("at")))), key=lambda pair: (pair[0], pair[1].get("record_id", "")))
        gaps = [(b[0] - a[0]).total_seconds() for a, b in zip(ordered, ordered[1:])]
        result.update((("analysis", "event_gaps"), ("gap_count", len(gaps)), ("shortest_gap_seconds", min(gaps) if gaps else None), ("longest_gap_seconds", max(gaps) if gaps else None), ("median_gap_seconds", sorted(gaps)[len(gaps)//2] if gaps else None)))
        result["analysis"] = "event_gaps"
        return result
    if analysis == "cadence":
        instants = [_instant(row.get("at")) for row in rows]; instants = [v for v in instants if v]
        span = (max(instants) - min(instants)).total_seconds() if len(instants) > 1 else 0
        days = Counter(value.date().isoformat() for value in instants)
        result.update((("analysis", "event_cadence"), ("observed_span_seconds", span), ("events_per_day", len(rows) / (span / 86400) if span > 0 else None), ("events_per_hour", len(rows) / (span / 3600) if span > 0 else None), ("active_day_count", len(days)), ("max_events_on_active_day", max(days.values()) if days else 0), ("first_active_day", min(days) if days else None), ("last_active_day", max(days) if days else None)))
        return result
    if analysis == "oscillation":
        transitions = []
        for row in rows:
            if row.get("event") in ("status_changed", "completed", "reopened", "canceled"):
                before, after = _payload(row, "before_status"), _payload(row, "after_status")
                if before and after and before != after: transitions.append((before, after, row))
        matches = [((a[0], a[1]), (a[2].get("record_id"), b[2].get("record_id"), c[2].get("record_id"))) for a, b, c in zip(transitions, transitions[1:], transitions[2:]) if a[1] == c[0] and a[0] == c[1]]
        result.update((("analysis", "status_oscillation"), ("oscillation_count", len(matches)), ("oscillations", [OrderedDict((("pair", list(pair)), ("event_ids", list(ids)))) for pair, ids in matches])))
        return result
    if analysis == "provenance":
        counts, sources, missing = Counter(), Counter(), 0
        for row in rows:
            payload = row.get("payload") or {}; actor = _payload(row, "actor") or _payload(row, "author") or _payload(row, "user")
            source = _payload(row, "source")
            if actor: counts[actor] += 1
            else: missing += 1
            if source: sources[source] += 1
        result.update((("analysis", "provenance"), ("actor_counts", OrderedDict((k, counts[k]) for k in sorted(counts))), ("source_counts", OrderedDict((k, sources[k]) for k in sorted(sources))), ("missing_provenance_count", missing)))
        return result
    if analysis == "schedule":
        fields, directions = Counter(), Counter()
        for row in rows:
            if row.get("event") != "schedule_changed": continue
            field = _payload(row, "field"); fields[field] += 1
            before, after = _payload(row, "before"), _payload(row, "after")
            if not before and after: directions["set"] += 1
            elif before and not after: directions["cleared"] += 1
            else: directions["changed"] += 1
        result.update((("analysis", "schedule_revision"), ("field_change_counts", OrderedDict((k, fields[k]) for k in sorted(fields))), ("change_categories", OrderedDict((k, directions[k]) for k in sorted(directions)))))
        return result
    if analysis == "schedule_lead_time":
        completed = next((row for row in rows if row.get("event") == "completed"), None)
        changes = [row for row in rows if row.get("event") == "schedule_changed" and _instant(row.get("at")) and completed and _instant(row.get("at")) <= _instant(completed.get("at"))]
        result["analysis"] = "schedule_completion_lead_time"
        result["completion_at"] = completed.get("at") if completed else None
        result["last_schedule_change"] = changes[-1].get("at") if changes else None
        result["lead_time_seconds"] = ((_instant(completed.get("at")) - _instant(changes[-1].get("at"))).total_seconds() if changes and completed else None)
        result["schedule_change_state"] = "observed" if changes else "none_observed"
        return result
    if analysis == "progress":
        values = []
        for row in rows:
            if row.get("record_kind") != "progress_event": continue
            raw = _payload(row, "after_progress")
            try: values.append((float(raw.rstrip("%")) / (100 if raw.endswith("%") else 1), row))
            except (TypeError, ValueError): pass
        deltas = [b[0] - a[0] for a, b in zip(values, values[1:])]
        result.update((("analysis", "progress_velocity"), ("first_progress", values[0][0] if values else None), ("last_progress", values[-1][0] if values else None), ("total_delta", values[-1][0] - values[0][0] if len(values) > 1 else 0), ("positive_delta_count", sum(value > 0 for value in deltas)), ("negative_delta_count", sum(value < 0 for value in deltas)), ("zero_delta_count", sum(value == 0 for value in deltas))))
        return result
    if analysis == "effort":
        from .ticket_activity import normalize_duration
        entries = []
        for row in rows:
            if row.get("record_kind") != "time_entry": continue
            try: entries.append((normalize_duration(_payload(row, "elapsed"))[1], row))
            except ValueError: pass
        activities = Counter(_payload(row, "activity") for _, row in entries)
        result.update((("analysis", "ticket_effort"), ("entry_count", len(entries)), ("total_elapsed_seconds", sum(value for value, _ in entries)), ("shortest_entry_seconds", min((value for value, _ in entries), default=None)), ("longest_entry_seconds", max((value for value, _ in entries), default=None)), ("activity_seconds", OrderedDict((key, sum(value for value, row in entries if _payload(row, "activity") == key)) for key in sorted(activities)))))
        return result
    if analysis == "due_variance":
        completed = next((row for row in rows if row.get("event") == "completed"), None)
        due = None
        for row in rows:
            if row.get("event") == "schedule_changed" and _payload(row, "field") == "due":
                due = _payload(row, "after") or None
        result["analysis"] = "due_completion_variance"
        result["due_at_completion"] = due
        result["completion_at"] = completed.get("at") if completed else None
        due_time, completion_time = _instant(due), _instant(completed.get("at")) if completed else None
        if due_time and completion_time:
            result["variance_seconds"] = (completion_time - due_time).total_seconds()
            result["classification"] = "before_due" if completion_time < due_time else "at_due" if completion_time == due_time else "after_due"
        else:
            result["variance_seconds"] = None; result["classification"] = "unavailable"; result["limitations"].append("due_at_completion_unavailable")
        return result
    if analysis == "relation":
        added, removed = Counter(), Counter()
        for row in rows:
            if row.get("event") == "relation_added": added[_payload(row, "relation")] += 1
            elif row.get("event") == "relation_removed": removed[_payload(row, "relation")] += 1
        result.update((("analysis", "relation_churn"), ("added", OrderedDict((k, added[k]) for k in sorted(added))), ("removed", OrderedDict((k, removed[k]) for k in sorted(removed)))))
        return result
    raise ValueError("Unknown lifecycle analytics %r." % analysis)


def workspace_lifecycle_stats(items, id_key="id", limit=500, since=None, until=None, duration=False):
    """Compose per-item summaries; never scans or invents history independently."""
    from .native_timeline import _is_history, _values, native_timeline
    targets = sorted({str(value) for item in items if not _is_history(item) for value in _values(item, id_key)})[:int(limit)]
    summaries = []
    for item_id in targets:
        timeline = native_timeline(items, item_id, id_key=id_key, limit=500, since=since, until=until)
        summary = lifecycle_analytics(timeline, "duration" if duration else "summary")
        summaries.append(summary)
    result = OrderedDict((("analysis", "workspace_lifecycle_stats"), ("scanned_item_count", len(targets)), ("items_with_native_history_count", sum(row["observed_event_count"] > 0 for row in summaries)), ("summaries", summaries), ("truncated", len(targets) >= int(limit))))
    if duration:
        values = sorted(row["duration_seconds"] for row in summaries if row.get("duration_seconds") is not None)
        result["duration_distribution"] = OrderedDict((("eligible_count", len(values)), ("unavailable_count", len(summaries) - len(values)), ("min_seconds", values[0] if values else None), ("median_seconds", values[len(values)//2] if values else None), ("mean_seconds", sum(values) / len(values) if values else None), ("max_seconds", values[-1] if values else None)))
    return result


def compare_lifecycle_windows(timeline_a, timeline_b):
    """Compare two independently filtered summaries using absolute deltas."""
    a, b = lifecycle_summary(timeline_a), lifecycle_summary(timeline_b)
    metrics = ("observed_event_count", "status_transition_count", "schedule_change_count", "relation_change_count", "completed_count", "reopened_count")
    return OrderedDict((("analysis", "lifecycle_window_comparison"), ("window_a", a), ("window_b", b), ("absolute_deltas", OrderedDict((key, b[key] - a[key]) for key in metrics)), ("limitations", sorted(set(a["limitations"] + b["limitations"])))) )
