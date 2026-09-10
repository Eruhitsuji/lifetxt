"""Bounded, deterministic Timeline over native semantic history records."""

from __future__ import unicode_literals

import datetime
from collections import OrderedDict

from .native_history import (
    is_item_event,
    item_event_history_diagnostics,
    native_history_completeness,
    normalize_native_events,
)
from .progress_history import is_progress_event, progress_history_diagnostics
from .ticket_activity import (
    is_ticket_event,
    is_time_entry,
    validate_ticket_history,
)
from .timeutil import parse_iso_date, parse_iso_datetime


DEFAULT_LIMIT = 100
MAX_LIMIT = 500
_KIND_ORDER = {
    "item_event": 0,
    "progress_event": 1,
    "ticket_event": 2,
    "time_entry": 3,
}


def _values(item, key):
    return [str(value) for value in (getattr(item, "details", {}).get(key) or [])]


def _first(item, key, default=None):
    values = _values(item, key)
    return values[0] if values else default


def _is_history(item):
    return (
        is_item_event(item)
        or is_progress_event(item)
        or is_ticket_event(item)
        or is_time_entry(item)
    )


def _sort_time(value):
    parsed = parse_iso_datetime(str(value or ""))
    if parsed is None:
        date = parse_iso_date(str(value or ""))
        if date is None:
            return (1, str(value or ""))
        parsed = datetime.datetime.combine(date, datetime.time.min).replace(
            tzinfo=datetime.timezone.utc
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return (1, str(value or ""))
    return (0, parsed.astimezone(datetime.timezone.utc).isoformat())


def _sort_key(row):
    sequence = row.get("sequence")
    return (
        _sort_time(row.get("at")),
        _KIND_ORDER.get(row.get("record_kind"), 99),
        sequence if isinstance(sequence, int) else 2**31,
        row.get("record_id") or "",
    )


def _diagnostic_value(row):
    return OrderedDict(
        (
            ("severity", row.severity),
            ("code", row.code),
            ("message", row.message),
            ("source", row.source),
            ("line", row.line),
        )
    )


def native_timeline(items, target_id, id_key="id", limit=DEFAULT_LIMIT):
    """Build one bounded read model without consulting or composing Git."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise ValueError("Timeline limit must be an integer.")
    if limit < 0 or limit > MAX_LIMIT:
        raise ValueError("Timeline limit must be between 0 and %d." % MAX_LIMIT)
    target_id = str(target_id)
    targets = [
        item
        for item in items
        if not _is_history(item) and target_id in _values(item, id_key)
    ]
    if len(targets) != 1:
        raise ValueError(
            "Expected exactly one item with %s:%s, found %d."
            % (id_key, target_id, len(targets))
        )
    target = targets[0]
    history = [
        item
        for item in items
        if _is_history(item) and str(_first(item, "parent", "")) == target_id
    ]
    relevant = [target] + history
    diagnostics = []
    if any(is_item_event(item) for item in history):
        diagnostics.extend(item_event_history_diagnostics(relevant, id_key=id_key))
    if any(is_progress_event(item) for item in history):
        diagnostics.extend(progress_history_diagnostics(relevant, id_key=id_key))
    if any(is_ticket_event(item) or is_time_entry(item) for item in history):
        diagnostics.extend(validate_ticket_history(relevant, key=id_key))

    normalized = sorted(normalize_native_events(history, target_id), key=_sort_key)
    valid = [row for row in normalized if row["valid"]]
    invalid = [row for row in normalized if not row["valid"]]
    total_valid = len(valid)
    selected = valid[:limit]
    truncated = total_valid > len(selected)
    completeness = native_history_completeness(relevant, target_id, id_key=id_key)
    limitations = []
    if not normalized:
        limitations.append("no_native_history")
    for domain, report in completeness.items():
        if report.get("coverage") not in ("none",) and not report.get("complete"):
            limitations.append("%s_history_incomplete" % domain)
    if diagnostics:
        limitations.append("history_diagnostics_present")
    if invalid:
        limitations.append("malformed_events_excluded")
    if truncated:
        limitations.append("event_limit_truncated")
    limitations = sorted(set(limitations))
    return OrderedDict(
        (
            ("schema", "temporal-timeline-v1"),
            ("target_id", target_id),
            (
                "target",
                OrderedDict(
                    (
                        ("title", target.title),
                        ("kind", target.kind),
                        ("status", target.status),
                    )
                ),
            ),
            ("source", "native_life_txt"),
            ("git_composed", False),
            (
                "bounds",
                OrderedDict(
                    (
                        ("limit", limit),
                        ("total_valid_events", total_valid),
                        ("returned_events", len(selected)),
                        ("truncated", truncated),
                    )
                ),
            ),
            ("complete", bool(normalized and not limitations)),
            ("limitations", limitations),
            ("completeness", completeness),
            ("events", selected),
            ("invalid_events", invalid),
            ("diagnostics", [_diagnostic_value(row) for row in diagnostics]),
        )
    )
