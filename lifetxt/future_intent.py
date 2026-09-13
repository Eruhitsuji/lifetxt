"""Bounded, read-only Future Intent Snapshot."""

from collections import OrderedDict

from .timeutil import parse_iso_datetime


def future_intent_snapshot(items, cutoff, until=None, limit=100, id_key="id"):
    start = parse_iso_datetime(str(cutoff))
    if start is None or start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("cutoff must be an offset-aware ISO timestamp")
    end = parse_iso_datetime(str(until)) if until else None
    if end and (end.tzinfo is None or end.utcoffset() is None):
        raise ValueError("until must be an offset-aware ISO timestamp")
    rows = []
    for item in items:
        values = []
        for field in ("do", "on", "at", "due", "from", "to"):
            for value in item.details.get(field, []):
                parsed = parse_iso_datetime(str(value))
                if parsed is None or parsed < start or (end and parsed > end):
                    continue
                values.append((parsed, field, str(value)))
        if not values:
            continue
        values.sort(key=lambda value: (value[0], value[1], value[2]))
        ids = [str(value) for value in item.details.get(id_key, [])]
        rows.append(
            OrderedDict(
                (
                    ("id", ids[0] if ids else None),
                    ("title", item.title),
                    ("kind", item.kind),
                    ("intent", values[0][1]),
                    ("target_time", values[0][2]),
                    ("evidence_status", "explicit"),
                    ("source", getattr(item, "source", None)),
                )
            )
        )
    rows.sort(key=lambda row: (row["target_time"], row["id"] or ""))
    truncated = len(rows) > int(limit)
    return OrderedDict(
        (
            ("schema", "future-intent-snapshot-v1"),
            ("cutoff", str(cutoff)),
            ("until", str(until) if until else None),
            ("items", rows[: int(limit)]),
            ("count", min(len(rows), int(limit))),
            (
                "bounds",
                OrderedDict(
                    (
                        ("limit", int(limit)),
                        ("total", len(rows)),
                        ("truncated", truncated),
                    )
                ),
            ),
            ("complete", not truncated),
            ("limitations", []),
        )
    )
