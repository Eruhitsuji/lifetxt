"""Derived, read-only free/busy interval and overlap detection (#673).

Reuses :mod:`lifetxt.agenda`'s existing occurrence-timing engine
(:func:`lifetxt.agenda.item_time_matches`) rather than re-deriving how
``from:``/``to:``/``at:``/``on:`` values resolve to concrete date/time
spans -- this module only adds free/busy interval algebra and pairwise
overlap detection on top of matches that engine already computes.

Scope for this first slice (see :mod:`lifetxt.temporal_context`'s own
``overlap``/near-window notes, which this closes):

- Only ``E`` (Event) and ``R`` (Reminder) items are considered. Other kinds
  (Task, Status, ...) do not represent scheduled time and are ignored.
- Only ``from:``/``to:``, ``at:``, and ``on:`` matches count toward busy
  time. ``notify_from:``/``notify_to:`` and point keys such as ``due:``/
  ``do:`` are reminders/deadlines, not attendance, and are excluded.
- Recurring items (``repeat:``) are out of scope for this slice and are
  reported as a non-fatal ``skipped_recurring`` diagnostic rather than
  silently ignored or (incorrectly) expanded.
- A zero-duration match (a bare ``at:`` instant, or a ``from:``/``to:``
  value with no matching counterpart) never occupies busy time -- a
  zero-width span cannot exclude anything from being free -- but is still
  surfaced as an ``instants`` entry so it is not silently dropped.
- Missing/invalid ``from:``/``to:``/``at:``/``on:`` values are reported as
  diagnostics; they are never silently ignored or silently treated as
  free or busy.

Nothing here is persisted back into life.txt. This is a pure read-only
report, matching ``lifetxt temporal``/``lifetxt integrity``.
"""

from __future__ import unicode_literals

from collections import OrderedDict
from datetime import datetime, timedelta

from .agenda import item_time_matches
from .timeutil import format_datetime, parse_date, parse_datetime, parse_time


#: Item kinds that can occupy scheduled time. Matches the issue's own scope
#: ("`E`/`R` items with `from:`/`to:`/`at:`").
BUSY_KINDS = ("E", "R")

#: item_time_matches() match keys that represent attendance/occupied time,
#: as opposed to reminder windows (notify_from/notify_to) or point-in-time
#: deadlines (due/do/moved_to/notify_at), which are excluded from this
#: first slice.
BUSY_MATCH_KEYS = frozenset(("from", "to", "from/to", "at", "on"))

#: Detail keys inspected directly for missing/invalid-value diagnostics,
#: independent of whether item_time_matches() found any match for them.
_TIME_DETAIL_KEYS = ("from", "to", "at", "on")


def _naive(value):
    """Strip an explicit UTC offset for interval arithmetic, converting to
    the host's local wall time first.

    Mixing offset-aware and offset-naive datetimes raises ``TypeError`` on
    comparison. Matches almost never carry an explicit offset in practice
    (life.txt datetimes are local by convention), but a value that does
    must not crash this module; it is normalized the same way
    :func:`lifetxt.timeutil.comparison_datetime` documents doing for
    "legacy naive comparisons".
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _ref(item):
    return OrderedDict(
        (
            ("title", item.title),
            ("kind", item.kind),
            ("status", item.status),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _diagnostic(code, message, item, **extra):
    diag = OrderedDict((("code", code), ("message", message), ("item", _ref(item))))
    for key, value in extra.items():
        diag[key] = value
    return diag


def _value_diagnostics(item):
    """Detect unparseable from:/to:/at:/on: detail values on one item.

    Reuses the exact parsers item_time_matches() itself uses
    (parse_datetime/parse_time/parse_date), so a value flagged here is
    genuinely one item_time_matches() could not resolve, not a
    freebusy-specific re-implementation of validity.
    """
    diags = []
    for key in ("from", "to"):
        for value in item.details.get(key, []):
            if parse_datetime(value) is None:
                diags.append(
                    _diagnostic(
                        "invalid_time_value",
                        "%s:%s could not be parsed as a datetime." % (key, value),
                        item,
                        detail_key=key,
                        value=value,
                    )
                )
    for value in item.details.get("at", []):
        if parse_datetime(value) is None and parse_time(value) is None:
            diags.append(
                _diagnostic(
                    "invalid_time_value",
                    "at:%s could not be parsed as a time or datetime." % value,
                    item,
                    detail_key="at",
                    value=value,
                )
            )
    for value in item.details.get("on", []):
        if parse_date(value) is None:
            diags.append(
                _diagnostic(
                    "invalid_time_value",
                    "on:%s could not be parsed as a date." % value,
                    item,
                    detail_key="on",
                    value=value,
                )
            )
    return diags


def _item_occurrences(item, range_start, range_end):
    """Return (busy, instants) for one item's matches within the window.

    busy: list of (start, end, key) with end > start, already clipped to
    [range_start, range_end).
    instants: list of (start, key) for zero-duration markers.

    Recurring items (repeat:) are excluded entirely -- item_time_matches()
    would expand them, but recurring-occurrence busy/free computation is
    out of scope for this slice (see module docstring); the caller reports
    this with a diagnostic rather than this function silently degrading.
    """
    busy = []
    instants = []
    for match in item_time_matches(item, range_start, range_end):
        if match["key"] not in BUSY_MATCH_KEYS:
            continue
        start = _naive(parse_datetime(match["start"]))
        if start is None:
            continue
        end_text = match.get("end")
        end = _naive(parse_datetime(end_text)) if end_text else None
        if end is None or end <= start:
            instants.append((start, match["key"]))
            continue
        clipped_start = max(start, range_start)
        clipped_end = min(end, range_end)
        if clipped_end <= clipped_start:
            continue
        busy.append((clipped_start, clipped_end, match["key"]))
    return busy, instants


def _merge_intervals(intervals):
    """Merge overlapping/touching (start, end) tuples into disjoint spans."""
    if not intervals:
        return []
    ordered = sorted(intervals, key=lambda pair: (pair[0], pair[1]))
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _free_gaps(merged_busy, range_start, range_end):
    """Gaps in [range_start, range_end) not covered by merged_busy."""
    free = []
    cursor = range_start
    for start, end in merged_busy:
        if start > cursor:
            free.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < range_end:
        free.append((cursor, range_end))
    return free


def _day_windows(range_start, range_end, day_start_time, day_end_time):
    """One (day_start, day_end) datetime pair per calendar day the range spans.

    ``range_end`` is exclusive, so the last included day is the date of the
    instant just before it, not ``range_end.date()`` itself (a range ending
    exactly at midnight must not pull in a whole extra day with no time in
    it).
    """
    windows = []
    current = range_start.date()
    last = (range_end - timedelta(microseconds=1)).date()
    while current <= last:
        windows.append(
            (
                datetime.combine(current, day_start_time),
                datetime.combine(current, day_end_time),
            )
        )
        current = current + timedelta(days=1)
    return windows


def _clip_to_windows(intervals, windows):
    clipped = []
    for start, end in intervals:
        for window_start, window_end in windows:
            overlap_start = max(start, window_start)
            overlap_end = min(end, window_end)
            if overlap_end > overlap_start:
                clipped.append((overlap_start, overlap_end))
    clipped.sort()
    return clipped


def _compute_conflicts(busy_entries):
    """Pairwise overlaps between different items' busy entries.

    busy_entries must already be sorted by (start, end). Bounded to the
    entries active at any moment (an interval-sweep, not an all-pairs
    scan of the whole workspace) -- ``active`` only ever holds entries
    whose interval has not yet ended.
    """
    conflicts = []
    active = []
    for entry in busy_entries:
        active = [
            candidate for candidate in active if candidate["end"] > entry["start"]
        ]
        for other in active:
            if other["item"] is entry["item"]:
                continue
            conflicts.append(
                OrderedDict(
                    (
                        ("a", other["ref"]),
                        ("b", entry["ref"]),
                        ("start", format_datetime(max(other["start"], entry["start"]))),
                        ("end", format_datetime(min(other["end"], entry["end"]))),
                    )
                )
            )
        active.append(entry)
    return conflicts


def compute_freebusy(
    items,
    range_start,
    range_end,
    day_window=None,
):
    """Free/busy report for ``items`` within ``[range_start, range_end)``.

    ``day_window``, when given, is a ``(start_time, end_time)`` pair of
    ``datetime.time`` values; free intervals are additionally clipped to
    that daily window on every day the range spans (e.g. only report free
    time during working hours). Busy intervals and conflicts are always
    reported for the full range regardless of ``day_window``.
    """
    range_start = _naive(range_start)
    range_end = _naive(range_end)
    if range_end <= range_start:
        raise ValueError("Range end must be after range start.")

    diagnostics = []
    busy_entries = []
    instant_entries = []

    for item in items:
        if item.kind not in BUSY_KINDS:
            continue
        diagnostics.extend(_value_diagnostics(item))
        if not any(item.details.get(key) for key in _TIME_DETAIL_KEYS):
            diagnostics.append(
                _diagnostic(
                    "missing_time_detail",
                    "Item has no from:/to:/at:/on: detail; excluded from freebusy.",
                    item,
                )
            )
            continue
        if item.details.get("repeat"):
            diagnostics.append(
                _diagnostic(
                    "skipped_recurring",
                    "Recurring items (repeat:) are not expanded by freebusy "
                    "yet; excluded from busy/free computation.",
                    item,
                )
            )
            continue
        busy, instants = _item_occurrences(item, range_start, range_end)
        ref = _ref(item)
        for start, end, key in busy:
            busy_entries.append(
                OrderedDict(
                    (
                        ("start", start),
                        ("end", end),
                        ("source_field", key),
                        ("item", item),
                        ("ref", ref),
                    )
                )
            )
        for start, key in instants:
            instant_entries.append(
                OrderedDict(
                    (
                        ("at", format_datetime(start)),
                        ("source_field", key),
                        ("item", ref),
                    )
                )
            )

    busy_entries.sort(key=lambda entry: (entry["start"], entry["end"]))
    conflicts = _compute_conflicts(busy_entries)

    merged_busy = _merge_intervals(
        [(entry["start"], entry["end"]) for entry in busy_entries]
    )
    free = _free_gaps(merged_busy, range_start, range_end)
    if day_window is not None:
        day_start_time, day_end_time = day_window
        windows = _day_windows(range_start, range_end, day_start_time, day_end_time)
        free = _clip_to_windows(free, windows)

    return OrderedDict(
        (
            ("schema", "freebusy-v1"),
            ("range_start", format_datetime(range_start)),
            ("range_end", format_datetime(range_end)),
            (
                "busy",
                [
                    OrderedDict(
                        (
                            ("start", format_datetime(entry["start"])),
                            ("end", format_datetime(entry["end"])),
                            ("source_field", entry["source_field"]),
                            ("item", entry["ref"]),
                        )
                    )
                    for entry in busy_entries
                ],
            ),
            (
                "free",
                [
                    OrderedDict(
                        (
                            ("start", format_datetime(start)),
                            ("end", format_datetime(end)),
                        )
                    )
                    for start, end in free
                ],
            ),
            ("conflicts", conflicts),
            ("instants", instant_entries),
            ("diagnostics", diagnostics),
        )
    )
