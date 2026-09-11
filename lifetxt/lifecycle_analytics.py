"""Deterministic, read-only lifecycle analytics over a Native Timeline."""

from __future__ import annotations

import datetime
import statistics
from collections import Counter, OrderedDict

from .timeutil import parse_iso_date, parse_iso_datetime

STATUS_EVENTS = ("status_changed", "completed", "reopened", "canceled")


def _instant(value):
    parsed = parse_iso_datetime(str(value or ""))
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(datetime.timezone.utc)


def _date(value):
    parsed = parse_iso_date(str(value or ""))
    if parsed is not None:
        return parsed
    instant = _instant(value)
    return instant.date() if instant else None


def _policy_date(value, timezone_name):
    """Return the calendar date under the workspace policy."""
    if not value:
        return None
    parsed_date = parse_iso_date(str(value))
    if parsed_date is not None:
        return parsed_date
    instant = _instant(value)
    if instant is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        return instant.astimezone(ZoneInfo(timezone_name or "UTC")).date()
    except (KeyError, TypeError):
        return instant.date()


def _history_is_safe(result):
    return result["complete"] and not any(
        value in result["limitations"]
        for value in (
            "item_history_incomplete",
            "history_diagnostics_present",
            "malformed_events_excluded",
        )
    )


def _rows_are_contiguous(previous, current):
    first, second = previous.get("sequence"), current.get("sequence")
    if first is None or second is None:
        return True
    try:
        delta = int(second) - int(first)
        return 0 <= delta <= 1
    except (TypeError, ValueError):
        return False


def _temporal_shift(before, after, timezone_name):
    before_instant, after_instant = _instant(before), _instant(after)
    if before_instant and after_instant:
        seconds = (after_instant - before_instant).total_seconds()
        return seconds, seconds / 86400.0
    before_date = _policy_date(before, timezone_name)
    after_date = _policy_date(after, timezone_name)
    if before_date and after_date:
        days = (after_date - before_date).days
        return days * 86400.0, float(days)
    return None, None


def _payload(row, key, default=None):
    values = (row.get("payload") or {}).get(key) or []
    return str(values[0]) if values else default


def _rows(timeline):
    source = timeline.get("_all_valid_events", timeline.get("events", []))
    rows = [row for row in source if row.get("valid", True)]
    max_time = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
    return sorted(rows, key=lambda row: (_instant(row.get("at")) or max_time, row.get("sequence") or 0, str(row.get("record_id", ""))))


def _evidence(row):
    return OrderedDict((("record_id", row.get("record_id")), ("at", row.get("at"))))


def _base(timeline, rows):
    types = Counter(str(row.get("event", "")) for row in rows)
    timed = [_instant(row.get("at")) for row in rows if _instant(row.get("at"))]
    limitations = list(timeline.get("limitations", []))
    if "_all_valid_events" in timeline:
        limitations = [value for value in limitations if value != "event_limit_truncated"]
    return OrderedDict((("analysis_schema", "lifecycle-analytics-v1"), ("target_id", timeline.get("target_id")), ("observed_event_count", len(rows)), ("event_counts", OrderedDict((key, types[key]) for key in sorted(types))), ("first_event_at", min(timed).isoformat().replace("+00:00", "Z") if timed else None), ("last_event_at", max(timed).isoformat().replace("+00:00", "Z") if timed else None), ("status_transition_count", sum(row.get("event") in STATUS_EVENTS for row in rows)), ("schedule_change_count", sum(row.get("event") == "schedule_changed" for row in rows)), ("relation_change_count", sum(row.get("event") in ("relation_added", "relation_removed") for row in rows)), ("completed_count", sum(row.get("event") == "completed" for row in rows)), ("reopened_count", sum(row.get("event") == "reopened" for row in rows)), ("complete", bool(timeline.get("complete")) or ("_all_valid_events" in timeline and not limitations)), ("limitations", limitations), ("diagnostics", list(timeline.get("diagnostics", [])))))


def _limit(result, value):
    if value not in result["limitations"]:
        result["limitations"].append(value)


def lifecycle_summary(timeline):
    result = _base(timeline, _rows(timeline))
    result["analysis"] = "lifecycle_summary"
    result["completeness"] = timeline.get("completeness", OrderedDict())
    return result


def _transitions(rows):
    result = []
    for row in rows:
        if row.get("event") not in STATUS_EVENTS:
            continue
        before, after = _payload(row, "before_status"), _payload(row, "after_status")
        if before and after and before != after:
            result.append((before, after, row))
    return result


def _median(values):
    return statistics.median(values) if values else None


def lifecycle_analytics(timeline, analysis="summary", timezone_name="UTC"):
    rows = _rows(timeline)
    result = lifecycle_summary(timeline)
    if analysis in (None, "summary"):
        return result
    if analysis == "duration":
        created = next((row for row in rows if row.get("event") == "created"), None)
        completed = next((row for row in rows if row.get("event") == "completed"), None)
        start, end = (_instant(created.get("at")) if created else None), (_instant(completed.get("at")) if completed else None)
        result.update((("analysis", "created_to_completed_duration"), ("created_at", created.get("at") if created else None), ("first_completed_at", completed.get("at") if completed else None), ("duration_seconds", (end - start).total_seconds() if start and end and end >= start else None), ("completion_event_count", result["completed_count"])))
        if start is None: _limit(result, "created_evidence_unavailable")
        if end is None: _limit(result, "completed_evidence_unavailable")
        if start and end and end < start: _limit(result, "completion_before_creation")
        return result
    if analysis == "transitions":
        transitions = _transitions(rows); counts = Counter("%s -> %s" % (a, b) for a, b, _ in transitions)
        result.update((("analysis", "status_transition_matrix"), ("transitions", OrderedDict((key, counts[key]) for key in sorted(counts))), ("transition_events", [_evidence(row) for _, _, row in transitions])))
        return result
    if analysis == "status_dwell":
        dwell, state, opened, unknown_seconds, previous = Counter(), None, None, 0, None
        for row in rows:
            if row.get("event") not in ("created",) + STATUS_EVENTS: continue
            at, after = _instant(row.get("at")), _payload(row, "after_status")
            if state and opened and at and at >= opened:
                seconds = (at - opened).total_seconds()
                if _history_is_safe(result) and (previous is None or _rows_are_contiguous(previous, row)):
                    dwell[state] += seconds
                else:
                    unknown_seconds += seconds
            if after: state, opened = after, at
            previous = row
        result.update((("analysis", "status_dwell"), ("dwell_seconds", OrderedDict((key, dwell[key]) for key in sorted(dwell))), ("unknown_dwell_seconds", unknown_seconds), ("open_interval", bool(state))))
        if unknown_seconds: _limit(result, "dwell_interval_unavailable")
        if state: _limit(result, "open_status_interval")
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
        result.update((("analysis", "completion_reopen_cycles"), ("cycle_count", cycles), ("recovery_count", recoveries), ("first_completion_at", next((r.get("at") for r in rows if r.get("event") == "completed"), None)), ("latest_completion_at", next((r.get("at") for r in reversed(rows) if r.get("event") == "completed"), None)), ("latest_reopen_at", next((r.get("at") for r in reversed(rows) if r.get("event") == "reopened"), None))))
        if not result["complete"]: _limit(result, "history_incomplete")
        return result
    if analysis == "gaps":
        ordered = [(value, row) for row in rows if (value := _instant(row.get("at")))]; gaps = [(b[0] - a[0]).total_seconds() for a, b in zip(ordered, ordered[1:])]
        largest = sorted(enumerate(gaps), key=lambda pair: (-pair[1], pair[0]))[:10]
        result.update((("analysis", "event_gaps"), ("gap_count", len(gaps)), ("shortest_gap_seconds", min(gaps) if gaps else None), ("longest_gap_seconds", max(gaps) if gaps else None), ("median_gap_seconds", _median(gaps)), ("observed_span_seconds", (ordered[-1][0] - ordered[0][0]).total_seconds() if len(ordered) > 1 else 0), ("gaps", [OrderedDict((("seconds", gaps[i]), ("before", _evidence(ordered[i][1])), ("after", _evidence(ordered[i + 1][1])))) for i, _ in largest])))
        if not _history_is_safe(result): _limit(result, "gap_metrics_not_authoritative")
        return result
    if analysis == "cadence":
        instants = [_instant(row.get("at")) for row in rows]; instants = [value for value in instants if value]; span = (max(instants) - min(instants)).total_seconds() if len(instants) > 1 else 0
        try:
            from zoneinfo import ZoneInfo
            display_zone = ZoneInfo(timezone_name or "UTC")
        except (KeyError, TypeError):
            display_zone = datetime.timezone.utc
            _limit(result, "timezone_unavailable")
        days = Counter(value.astimezone(display_zone).date().isoformat() for value in instants)
        result.update((("analysis", "event_cadence"), ("observed_span_seconds", span), ("event_count", len(rows)), ("events_per_day", len(instants) / (span / 86400) if span else None), ("events_per_hour", len(instants) / (span / 3600) if span else None), ("active_day_count", len(days)), ("max_events_on_active_day", max(days.values()) if days else 0), ("first_active_day", min(days) if days else None), ("last_active_day", max(days) if days else None)))
        return result
    if analysis == "oscillation":
        transitions = _transitions(rows); matches = []
        unsafe_history = any(value in result["limitations"] for value in ("item_history_incomplete", "history_diagnostics_present", "malformed_events_excluded"))
        for first, second in zip(transitions, transitions[1:]):
            sequence_is_contiguous = _rows_are_contiguous(first[2], second[2])
            if not unsafe_history and sequence_is_contiguous and first[0] == second[1] and first[1] == second[0]:
                matches.append(OrderedDict((("pair", [first[0], first[1]]), ("event_ids", [first[2].get("record_id"), second[2].get("record_id")]), ("evidence", [_evidence(first[2]), _evidence(second[2])]))))
        result.update((("analysis", "status_oscillation"), ("oscillation_count", len(matches)), ("oscillations", matches))); return result
    if analysis == "provenance":
        actors, sources, kinds = Counter(), Counter(), Counter(); missing = 0; source_bounds = {}; actor_bounds = {}; evidence = []
        for row in rows:
            actor_field = next((field for field in ("actor", "author", "user") if _payload(row, field)), None)
            actor = _payload(row, actor_field) if actor_field else None; source = _payload(row, "source")
            if actor: actors[actor] += 1
            else: missing += 1
            if actor:
                actor_bounds.setdefault(actor, [row, row]); actor_bounds[actor][1] = row
            if source:
                sources[source] += 1
                source_bounds.setdefault(source, [row, row]); source_bounds[source][1] = row
            kinds[row.get("record_kind")] += 1
            if actor_field or source:
                evidence.append(OrderedDict((("record_id", row.get("record_id")), ("record_kind", row.get("record_kind")), ("field", actor_field or "source"), ("value", actor or source), ("at", row.get("at")))))
        source_first_last = OrderedDict()
        for key in sorted(source_bounds):
            source_first_last[key] = OrderedDict((("first", source_bounds[key][0].get("at")), ("last", source_bounds[key][1].get("at"))))
        actor_first_last = OrderedDict()
        for key in sorted(actor_bounds):
            field = next((name for name in ("actor", "author", "user") if _payload(actor_bounds[key][0], name)), None)
            actor_first_last[key] = OrderedDict((("field", field), ("first", _evidence(actor_bounds[key][0])), ("last", _evidence(actor_bounds[key][1])), ("count", actors[key])))
        result.update((("analysis", "provenance"), ("actor_counts", OrderedDict((key, actors[key]) for key in sorted(actors))), ("source_counts", OrderedDict((key, sources[key]) for key in sorted(sources))), ("record_kind_counts", OrderedDict((key, kinds[key]) for key in sorted(kinds))), ("source_first_last", source_first_last), ("actor_first_last", actor_first_last), ("provenance_evidence", evidence), ("missing_provenance_count", missing)))
        return result
    if analysis in ("schedule", "schedule_lead_time", "due_variance"):
        changes = [row for row in rows if row.get("event") == "schedule_changed"]
        if analysis == "schedule":
            fields, categories, first_last, field_shifts = Counter(), Counter(), {}, {}
            for row in changes:
                field = _payload(row, "field") or "unknown"; fields[field] += 1; before, after = _payload(row, "before"), _payload(row, "after"); categories["set" if not before and after else "cleared" if before and not after else "changed"] += 1; first_last.setdefault(field, [before, after]); first_last[field][1] = after
                seconds, days = _temporal_shift(before, after, timezone_name); field_shifts.setdefault(field, []).append((seconds, days, row))
            shifts = [days for values in field_shifts.values() for _, days, _ in values if days is not None]
            per_field = OrderedDict()
            for field in sorted(field_shifts):
                values = field_shifts[field]; comparable = [(seconds, days, row) for seconds, days, row in values if days is not None]
                per_field[field] = OrderedDict((("earlier_count", sum(days < 0 for _, days, _ in comparable)), ("later_count", sum(days > 0 for _, days, _ in comparable)), ("unchanged_count", sum(days == 0 for _, days, _ in comparable)), ("net_shift_days", sum(days for _, days, _ in comparable) if comparable else None), ("net_shift_seconds", sum(seconds for seconds, _, _ in comparable) if comparable else None), ("first_change", _evidence(values[0][2])), ("last_change", _evidence(values[-1][2])), ("incomparable_count", len(values) - len(comparable))))
            result.update((("analysis", "schedule_revision"), ("field_change_counts", OrderedDict((key, fields[key]) for key in sorted(fields))), ("change_categories", OrderedDict((key, categories[key]) for key in sorted(categories))), ("first_last_values", OrderedDict((key, OrderedDict((("first", first_last[key][0]), ("last", first_last[key][1])))) for key in sorted(first_last))), ("field_shifts", per_field), ("earlier_count", sum(value < 0 for value in shifts)), ("later_count", sum(value > 0 for value in shifts)), ("unchanged_count", sum(value == 0 for value in shifts)), ("net_shift_days", sum(shifts) if shifts else None))); return result
        completed = next((row for row in rows if row.get("event") == "completed"), None); completion_at = _instant(completed.get("at")) if completed else None; prior = [row for row in changes if completion_at and _instant(row.get("at")) and _instant(row.get("at")) <= completion_at]; last = prior[-1] if prior else None
        if analysis == "schedule_lead_time":
            state = "observed" if last else "none_observed" if result["complete"] else "unknown"
            result.update((("analysis", "schedule_completion_lead_time"), ("completion_at", completed.get("at") if completed else None), ("last_schedule_change", last.get("at") if last else None), ("affected_field", _payload(last, "field") if last else None), ("lead_time_seconds", (completion_at - _instant(last.get("at"))).total_seconds() if last and completion_at else None), ("schedule_change_state", state))); return result
        due_rows = [row for row in prior if _payload(row, "field") == "due"]; due = _payload(due_rows[-1], "after") if due_rows else None; due_date = _policy_date(due, timezone_name); completion_date = _policy_date(completed.get("at") if completed else None, timezone_name); classification = "unavailable" if not _history_is_safe(result) else ("before_due" if due_date and completion_date and completion_date < due_date else "at_due" if due_date and completion_date == due_date else "after_due" if due_date and completion_date else "unavailable")
        result.update((("analysis", "due_completion_variance"), ("due_at_completion", due), ("completion_at", completed.get("at") if completed else None), ("variance_days", (completion_date - due_date).days if classification != "unavailable" and due_date and completion_date else None), ("classification", classification)))
        result["affected_field"] = "due" if due_rows else None
        if classification == "unavailable": _limit(result, "due_at_completion_unavailable")
        return result
    if analysis == "progress":
        from .progress import parse_progress
        values = []
        for row in rows:
            if row.get("record_kind") != "progress_event": continue
            try: values.append((parse_progress(_payload(row, "after_progress")).percent, row))
            except (TypeError, ValueError): _limit(result, "invalid_progress_value")
        values.sort(key=lambda pair: (_instant(pair[1].get("at")) or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc), pair[1].get("sequence") or 0)); deltas = [b[0] - a[0] for a, b in zip(values, values[1:])]; elapsed = (_instant(values[-1][1].get("at")) - _instant(values[0][1].get("at"))).total_seconds() if len(values) > 1 and _instant(values[0][1].get("at")) and _instant(values[-1][1].get("at")) else None
        largest = sorted(enumerate(deltas), key=lambda pair: (-abs(pair[1]), pair[0]))[:10]
        def delta_evidence(index):
            return OrderedDict((("delta", deltas[index]), ("before", _evidence(values[index][1])), ("after", _evidence(values[index + 1][1]))))
        positive = [index for index, value in enumerate(deltas) if value > 0]; negative = [index for index, value in enumerate(deltas) if value < 0]
        result.update((("analysis", "progress_velocity"), ("first_progress", values[0][0] if values else None), ("last_progress", values[-1][0] if values else None), ("total_delta", values[-1][0] - values[0][0] if len(values) > 1 else None), ("elapsed_seconds", elapsed), ("rate_per_day", (values[-1][0] - values[0][0]) / (elapsed / 86400) if elapsed and _history_is_safe(result) else None), ("positive_delta_count", sum(value > 0 for value in deltas)), ("negative_delta_count", sum(value < 0 for value in deltas)), ("zero_delta_count", sum(value == 0 for value in deltas)), ("largest_deltas", [delta_evidence(index) for index, _ in largest]), ("largest_positive_delta", delta_evidence(max(positive, key=lambda index: deltas[index])) if positive else None), ("largest_negative_delta", delta_evidence(min(negative, key=lambda index: deltas[index])) if negative else None)))
        if not result["complete"]: _limit(result, "history_incomplete")
        return result
    if analysis == "effort":
        from .ticket_activity import normalize_duration
        entries = []
        for row in rows:
            if row.get("record_kind") != "time_entry": continue
            try: entries.append((normalize_duration(_payload(row, "elapsed"))[1], row))
            except (TypeError, ValueError): _limit(result, "invalid_time_entry")
        values = [value for value, _ in entries]; activities = Counter(_payload(row, "activity") or "unknown" for _, row in entries); users = Counter(_payload(row, "user") or _payload(row, "author") or "unknown" for _, row in entries); entry_dates = sorted(set(_payload(row, "on") for _, row in entries if _payload(row, "on")))
        result.update((("analysis", "ticket_effort"), ("entry_count", len(entries)), ("total_elapsed_seconds", sum(values)), ("average_entry_seconds", sum(values) / len(values) if values else None), ("shortest_entry_seconds", min(values) if values else None), ("longest_entry_seconds", max(values) if values else None), ("activity_seconds", OrderedDict((key, sum(value for value, row in entries if (_payload(row, "activity") or "unknown") == key)) for key in sorted(activities))), ("user_entry_counts", OrderedDict((key, users[key]) for key in sorted(users))), ("user_seconds", OrderedDict((key, sum(value for value, row in entries if (_payload(row, "user") or _payload(row, "author") or "unknown") == key)) for key in sorted(users))), ("entry_dates", entry_dates), ("first_entry_date", entry_dates[0] if entry_dates else None), ("last_entry_date", entry_dates[-1] if entry_dates else None))); return result
    if analysis == "relation":
        added, removed, targets = Counter(), Counter(), Counter()
        changes = {}
        previous_change = {}
        round_trips = 0
        for row in rows:
            if row.get("event") not in ("relation_added", "relation_removed"):
                continue
            relation = _payload(row, "relation") or "unknown"; target = _payload(row, "target") or "unknown"; key = (relation, target)
            changes.setdefault(key, []).append(row)
            event = row.get("event")
            if previous_change.get(key) and previous_change[key] != event:
                round_trips += 1
                previous_change.pop(key, None)
            else:
                previous_change[key] = event
            if event == "relation_added":
                added[relation] += 1; targets[key] += 1
            elif event == "relation_removed":
                removed[relation] += 1
                targets[key] -= 1
        target_rows = []
        for key in sorted(changes):
            evidence = changes[key]
            target_rows.append(OrderedDict((("relation", key[0]), ("target", key[1]), ("change_count", len(evidence)), ("net", targets[key] if result["complete"] else None), ("first", _evidence(evidence[0])), ("last", _evidence(evidence[-1])))))
        relation_net = OrderedDict((key, added[key] - removed[key] if result["complete"] else None) for key in sorted(set(added) | set(removed)))
        result.update((("analysis", "relation_churn"), ("added", OrderedDict((key, added[key]) for key in sorted(added))), ("removed", OrderedDict((key, removed[key]) for key in sorted(removed))), ("net_by_relation", relation_net), ("target_net", target_rows), ("round_trip_count", round_trips), ("net_available", result["complete"]))); return result
    raise ValueError("Unknown lifecycle analytics %r." % analysis)


def workspace_lifecycle_stats(items, id_key="id", limit=500, since=None, until=None, duration=False, timezone_name="UTC"):
    from .native_timeline import _is_history, _values, native_timeline
    if int(limit) <= 0:
        raise ValueError("limit must be greater than zero")
    all_targets = sorted({str(value) for item in items if not _is_history(item) for value in _values(item, id_key)})
    targets = all_targets[:int(limit)]
    summaries = []
    for item_id in targets:
        timeline = native_timeline(items, item_id, id_key=id_key, limit=500, since=since, until=until, include_all_valid=True)
        summary = lifecycle_analytics(timeline, "duration" if duration else "summary", timezone_name)
        summary["completeness"] = timeline.get("completeness", {})
        summaries.append(summary)
    event_counts = Counter(); total = 0
    for summary in summaries: total += summary["observed_event_count"]; event_counts.update(summary["event_counts"])
    coverage = []
    for summary in summaries:
        state = "complete" if summary["complete"] else "partial" if summary["observed_event_count"] else "none"
        coverage.append(OrderedDict((("item_id", summary["target_id"]), ("state", state), ("event_count", summary["observed_event_count"]), ("reasons", list(summary["limitations"])))) )
    domain_states = {}
    reason_counts = {}
    for summary in summaries:
        for domain, report in (summary.get("completeness") or {}).items():
            state = "none" if report.get("coverage") in (None, "none") else "complete" if report.get("complete") else "partial"
            domain_states.setdefault(domain, Counter())[state] += 1
            for reason in report.get("diagnostic_codes", []) + summary.get("limitations", []):
                reason_counts.setdefault(domain, Counter())[str(reason)] += 1
    completeness_by_domain = OrderedDict()
    for domain in sorted(domain_states):
        completeness_by_domain[domain] = OrderedDict((("complete", domain_states[domain]["complete"]), ("partial", domain_states[domain]["partial"]), ("none", domain_states[domain]["none"]), ("reason_counts", OrderedDict((key, reason_counts.get(domain, Counter())[key]) for key in sorted(reason_counts.get(domain, {}))))))
    result = OrderedDict((("analysis", "workspace_lifecycle_stats"), ("scanned_item_count", len(targets)), ("items_with_native_history_count", sum(row["observed_event_count"] > 0 for row in summaries)), ("total_valid_event_count", total), ("event_type_counts", OrderedDict((key, event_counts[key]) for key in sorted(event_counts))), ("status_transition_count", sum(row["status_transition_count"] for row in summaries)), ("schedule_change_count", sum(row["schedule_change_count"] for row in summaries)), ("relation_change_count", sum(row["relation_change_count"] for row in summaries)), ("completed_count", sum(row["completed_count"] for row in summaries)), ("reopened_count", sum(row["reopened_count"] for row in summaries)), ("incomplete_item_count", sum(not row["complete"] for row in summaries)), ("coverage", coverage), ("coverage_by_domain", completeness_by_domain), ("summaries", summaries), ("truncated", len(all_targets) > int(limit))))
    if duration:
        values = sorted((row["duration_seconds"], row["target_id"]) for row in summaries if row.get("duration_seconds") is not None and _history_is_safe(row)); seconds = [value for value, _ in values]
        min_value = min(seconds) if seconds else None
        max_value = max(seconds) if seconds else None
        result["duration_distribution"] = OrderedDict((("eligible_count", len(seconds)), ("unavailable_count", len(summaries) - len(seconds)), ("min_seconds", min_value), ("median_seconds", _median(seconds)), ("mean_seconds", sum(seconds) / len(seconds) if seconds else None), ("max_seconds", max_value), ("example_item_ids", [item_id for _, item_id in values[:10]]), ("min_item_ids", [item_id for value, item_id in values if value == min_value]), ("max_item_ids", [item_id for value, item_id in values if value == max_value])))
        if result["incomplete_item_count"]: result.setdefault("limitations", []).append("incomplete_duration_excluded")
    if result["truncated"]: result.setdefault("limitations", []).append("workspace_items_truncated")
    return result


def compare_lifecycle_windows(timeline_a, timeline_b):
    a, b = lifecycle_summary(timeline_a), lifecycle_summary(timeline_b)
    metrics = ("observed_event_count", "status_transition_count", "schedule_change_count", "relation_change_count", "completed_count", "reopened_count")
    event_keys = sorted(set(a["event_counts"]) | set(b["event_counts"]))
    absolute_deltas = OrderedDict((key, b[key] - a[key]) for key in metrics)
    event_type_deltas = OrderedDict((key, b["event_counts"].get(key, 0) - a["event_counts"].get(key, 0)) for key in event_keys)
    return OrderedDict((("analysis", "lifecycle_window_comparison"), ("window_a", a), ("window_b", b), ("absolute_deltas", absolute_deltas), ("event_type_deltas", event_type_deltas), ("limitations", sorted(set(a["limitations"] + b["limitations"])))) )
