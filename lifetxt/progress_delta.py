"""Period-boundary delta semantics for authoritative progress history."""

from __future__ import unicode_literals

import datetime
from collections import OrderedDict

from .progress import parse_progress
from .progress_history import authoritative_progress_events, iter_progress_events
from .timeutil import parse_iso_datetime


PROGRESS_DELTA_SCHEMA = "lifetxt-progress-delta-v1"


def _first(item, key, default=None):
    values = getattr(item, "details", {}).get(key) or []
    return values[0] if values else default


def _aware(value, name):
    parsed = (
        value if isinstance(value, datetime.datetime) else parse_iso_datetime(value)
    )
    if not isinstance(parsed, datetime.datetime):
        raise ValueError("%s must be an ISO date-time." % name)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("%s must include a UTC offset." % name)
    return parsed


def _value_at(events, boundary):
    selected = None
    for event in events:
        at = _aware(_first(event, "at"), "progress event at")
        if at <= boundary:
            selected = event
        else:
            break
    if selected is None:
        return None
    raw = str(_first(selected, "after_progress"))
    return selected, parse_progress(raw)


def _boundary_value(value):
    if value is None:
        return None, None, None
    event, parsed = value
    return parsed.raw, parsed.ratio, str(_first(event, "at"))


def progress_delta(items, parent_id, start, end, id_key="id"):
    """Return the authoritative progress change over inclusive boundaries.

    The value at a boundary is the ``after_progress`` of the last valid event
    at or before that instant.  A current value or a later event's ``before``
    value is never used to guess a missing baseline.
    """
    start = _aware(start, "from boundary")
    end = _aware(end, "to boundary")
    if end < start:
        raise ValueError("to boundary must not be earlier than from boundary.")

    parent_id = str(parent_id)
    events = authoritative_progress_events(items, parent_id, id_key=id_key)
    if not events:
        reason = (
            "history_incomplete"
            if iter_progress_events(items, parent_id)
            else "no_history"
        )
        return _result(parent_id, start, end, None, None, reason)

    start_value = _value_at(events, start)
    end_value = _value_at(events, end)
    if start_value is None:
        return _result(parent_id, start, end, None, end_value, "start_unavailable")
    if end_value is None:
        return _result(parent_id, start, end, start_value, None, "end_unavailable")
    return _result(parent_id, start, end, start_value, end_value, None)


def _result(parent_id, start, end, start_value, end_value, reason):
    start_raw, start_ratio, start_at = _boundary_value(start_value)
    end_raw, end_ratio, end_at = _boundary_value(end_value)
    available = reason is None
    delta_ratio = _clean_number(end_ratio - start_ratio) if available else None
    return OrderedDict(
        [
            ("schema", PROGRESS_DELTA_SCHEMA),
            ("key", "progress"),
            ("item_id", str(parent_id)),
            ("from", start.isoformat()),
            ("to", end.isoformat()),
            ("available", available),
            ("reason", reason),
            ("start_raw", start_raw),
            ("start_ratio", start_ratio),
            ("start_at", start_at),
            ("end_raw", end_raw),
            ("end_ratio", end_ratio),
            ("end_at", end_at),
            ("delta_ratio", delta_ratio),
            (
                "delta_percentage_points",
                _clean_number(delta_ratio * 100.0)
                if delta_ratio is not None
                else None,
            ),
        ]
    )


def format_progress_delta(result):
    """Render the machine result without recomputing its semantics."""
    lines = ["progress %s" % result["item_id"]]
    if not result["available"]:
        lines.extend(
            [
                "  start: %s" % (result["start_raw"] or "n/a"),
                "  end:   %s" % (result["end_raw"] or "n/a"),
                "  delta: n/a (%s)" % result["reason"],
            ]
        )
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "  start: %s" % result["start_raw"],
            "  end:   %s" % result["end_raw"],
            "  delta: %s pp"
            % _signed_number(result["delta_percentage_points"]),
        ]
    )
    return "\n".join(lines) + "\n"


def _signed_number(value):
    text = "%.12g" % value
    return text if text.startswith("-") else "+" + text


def _clean_number(value):
    rounded = round(float(value), 12)
    return 0.0 if rounded == 0 else rounded
