"""Read-only importance and time-derived urgency for actionable tasks."""

from datetime import timedelta

from .timeutil import parse_date, parse_datetime
from .timezone_policy import date_boundaries, interpret_datetime, now

IMPORTANCE_VALUES = ("high", "normal", "low")
QUADRANTS = ("Q1", "Q2", "Q3", "Q4", "unclassified")


def classify_item(item, reference_time=None):
    """Return a derived classification; never mutate the source item.

    Date-only due values expire after the entire calendar day in the active
    workspace timezone. Datetimes retain explicit offsets when supplied.
    """
    if item.kind != "T" or item.status not in ("[ ]", "[/]"):
        return None
    reference = interpret_datetime(reference_time) if reference_time is not None else now()
    values = item.details.get("importance", [])
    importance = values[0] if len(values) == 1 and values[0] in IMPORTANCE_VALUES else None
    raw_due = item.details.get("due", [])
    urgency = "low"
    if raw_due:
        due = parse_date(raw_due[0])
        if due is not None:
            deadline = date_boundaries(due)[1]
        elif parse_datetime(raw_due[0]) is not None:
            deadline = interpret_datetime(raw_due[0])
        else:
            # A malformed deadline must not quietly rank as a distant deadline.
            return {"importance": importance, "urgency": "unknown", "quadrant": "unclassified"}
        remaining = deadline - reference
        if remaining < timedelta(0):
            urgency = "critical"
        elif remaining <= timedelta(hours=24):
            urgency = "high"
        elif remaining <= timedelta(days=7):
            urgency = "normal"
    if importance is None:
        quadrant = "unclassified"
    else:
        urgent = urgency in ("critical", "high", "normal")
        quadrant = ("Q1" if urgent else "Q2") if importance == "high" else ("Q3" if urgent else "Q4")
    return {"importance": importance, "urgency": urgency, "quadrant": quadrant}


def matrix_rows(items, reference_time=None, quadrant=None):
    """Group actionable tasks in stable source order."""
    if quadrant is not None and quadrant not in QUADRANTS:
        raise ValueError("Unknown quadrant: %s" % quadrant)
    groups = {name: [] for name in QUADRANTS}
    reference = reference_time if reference_time is not None else now()
    for item in items:
        result = classify_item(item, reference)
        if result is None or (quadrant is not None and result["quadrant"] != quadrant):
            continue
        groups[result["quadrant"]].append({
            "title": item.title,
            "status": item.status,
            "due": (item.details.get("due") or [None])[0],
            **result,
        })
    return groups
