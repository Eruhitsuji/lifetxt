"""Read-only importance and time-derived urgency for actionable tasks."""

from datetime import timedelta

from .timeutil import parse_date, parse_datetime
from .timezone_policy import date_boundaries, interpret_datetime, now

IMPORTANCE_VALUES = ("high", "normal", "low")
QUADRANTS = ("Q1", "Q2", "Q3", "Q4", "unclassified")
URGENCY_HIGH_WINDOW = timedelta(hours=24)
URGENCY_NORMAL_WINDOW = timedelta(days=7)
URGENT_URGENCY = ("critical", "high", "normal")


def _due_deadline(value):
    """Resolve a due value with the same date and timezone rules as the matrix."""
    due = parse_date(value)
    if due is not None:
        return date_boundaries(due)[1]
    if parse_datetime(value) is not None:
        return interpret_datetime(value)
    return None


def classify_item(item, reference_time=None):
    """Return a derived classification; never mutate the source item.

    Date-only due values expire after the entire calendar day in the active
    workspace timezone. Datetimes retain explicit offsets when supplied.
    """
    if item.kind != "T" or item.status not in ("[ ]", "[/]"):
        return None
    reference = (
        interpret_datetime(reference_time) if reference_time is not None else now()
    )
    values = item.details.get("importance", [])
    importance = (
        values[0] if len(values) == 1 and values[0] in IMPORTANCE_VALUES else None
    )
    raw_due = item.details.get("due", [])
    urgency = "low"
    if raw_due:
        deadline = _due_deadline(raw_due[0])
        if deadline is None:
            # A malformed deadline must not quietly rank as a distant deadline.
            return {
                "importance": importance,
                "urgency": "unknown",
                "quadrant": "unclassified",
            }
        remaining = deadline - reference
        if remaining < timedelta(0):
            urgency = "critical"
        elif remaining <= URGENCY_HIGH_WINDOW:
            urgency = "high"
        elif remaining <= URGENCY_NORMAL_WINDOW:
            urgency = "normal"
    if importance is None:
        quadrant = "unclassified"
    else:
        urgent = urgency in URGENT_URGENCY
        quadrant = (
            ("Q1" if urgent else "Q2")
            if importance == "high"
            else ("Q3" if urgent else "Q4")
        )
    return {"importance": importance, "urgency": urgency, "quadrant": quadrant}


def next_transition(item, reference_time=None):
    """Return the next future quadrant transition, without changing the item.

    The matrix's only time-driven quadrant boundary is the point at which a
    deadline enters the existing seven-day (``normal`` urgency) window.
    ``high`` and ``critical`` urgency remain on the same urgent side of the
    matrix, so their later thresholds do not create quadrant transitions.
    """
    current = classify_item(item, reference_time)
    if current is None or current["quadrant"] == "unclassified":
        return None

    raw_due = item.details.get("due", [])
    if not raw_due:
        return None
    deadline = _due_deadline(raw_due[0])
    if deadline is None:
        return None

    reference = (
        interpret_datetime(reference_time) if reference_time is not None else now()
    )
    transition_at = deadline - URGENCY_NORMAL_WINDOW
    if transition_at <= reference:
        return None

    future = classify_item(item, transition_at)
    if future is None or future["quadrant"] == current["quadrant"]:
        return None
    return {
        "next_at": transition_at.isoformat(),
        "next_quadrant": future["quadrant"],
    }


def matrix_rows(
    items,
    reference_time=None,
    quadrant=None,
    include_priority=False,
    include_horizon=False,
):
    """Group actionable tasks in stable source order."""
    if quadrant is not None and quadrant not in QUADRANTS:
        raise ValueError("Unknown quadrant: %s" % quadrant)
    groups = {name: [] for name in QUADRANTS}
    reference = reference_time if reference_time is not None else now()
    for item in items:
        result = classify_item(item, reference)
        if result is None or (quadrant is not None and result["quadrant"] != quadrant):
            continue
        row = {
            "title": item.title,
            "status": item.status,
            "due": (item.details.get("due") or [None])[0],
            **result,
        }
        if include_priority:
            row["priority"] = (item.details.get("priority") or [None])[0]
        if include_horizon:
            transition = next_transition(item, reference)
            row["next_at"] = transition["next_at"] if transition else None
            row["next_quadrant"] = transition["next_quadrant"] if transition else None
        groups[result["quadrant"]].append(row)
    return groups
