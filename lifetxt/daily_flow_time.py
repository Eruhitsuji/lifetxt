"""Workspace-time certification adapter for the read-only Daily Flow core.

Only constant-offset windows are certified. Original items and legacy engines
remain untouched; normalized copies contain workspace wall times for freebusy.
"""

from datetime import datetime, timedelta, timezone as utc_timezone

from .freebusy import compute_freebusy
from .model import Item
from .timeutil import parse_date, parse_datetime, parse_time
from .timezone_policy import (
    interpret_datetime,
    interpret_time,
    localize_datetime,
    timezone_info,
)


class OccupancyError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def plain(value):
    """Avoid LifeDateTime's legacy wall-time comparison overrides."""
    return datetime(
        value.year,
        value.month,
        value.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=value.tzinfo,
        fold=value.fold,
    )


def instant(value, zone):
    return plain(interpret_datetime(value, zone)).astimezone(utc_timezone.utc)


def wall(value, zone):
    return plain(value.astimezone(timezone_info(zone))).replace(tzinfo=None)


def stamp(value, zone):
    return value.astimezone(timezone_info(zone)).isoformat()


def constant_offset(start, end, zone):
    """Check the full inclusive span, not merely equal endpoint offsets.

    Lite rejects transitions. Half-hour samples cover IANA transition spacing;
    exact authored endpoints are checked by the shared fold/gap interpreter.
    Spans longer than two days cannot be certified here.
    """
    if end - start > timedelta(days=2):
        raise OccupancyError("unsupported_timezone_window")
    tz = timezone_info(zone)
    cursor = start
    offset = start.astimezone(tz).utcoffset()
    while cursor < end:
        if cursor.astimezone(tz).utcoffset() != offset:
            raise OccupancyError("unsupported_timezone_window")
        cursor = min(end, cursor + timedelta(minutes=30))
    if end.astimezone(tz).utcoffset() != offset:
        raise OccupancyError("unsupported_timezone_window")


def day_window(date, day_start, day_end, zone):
    if parse_time(day_start) is None or parse_time(day_end) is None:
        raise ValueError("Explicit day_start/day_end must be valid times.")
    start = plain(interpret_time(day_start, date, zone))
    end = plain(interpret_time(day_end, date, zone))
    if end.time().replace(tzinfo=None).isoformat() == "00:00:00":
        end = plain(interpret_time(day_end, date + timedelta(days=1), zone))
    start_utc = start.astimezone(utc_timezone.utc)
    end_utc = end.astimezone(utc_timezone.utc)
    if start.date() != date or end.date() not in (date, date + timedelta(days=1)):
        raise ValueError("Window must belong to the selected workspace day.")
    if end.date() != date and end.time().replace(tzinfo=None).isoformat() != "00:00:00":
        raise ValueError("Only the exclusive end may be next midnight.")
    if end_utc <= start_utc:
        raise ValueError("Window end must be after start.")
    return start_utc, end_utc


def deadline(value, zone):
    date = parse_date(value)
    if date is not None:
        # Shared matrix date-only deadline is the inclusive final microsecond.
        from .timezone_policy import date_boundaries

        return plain(date_boundaries(date, zone)[1]).astimezone(utc_timezone.utc)
    return instant(value, zone)


def release_time(value, zone):
    date = parse_date(value)
    if date is not None:
        return plain(
            localize_datetime(datetime.combine(date, datetime.min.time()), zone)
        ).astimezone(utc_timezone.utc)
    return instant(value, zone)


def normalized_event(item, date, start, end, zone):
    details = {key: list(values) for key, values in item.details.items()}
    if details.get("repeat"):
        raise OccupancyError("skipped_recurring")
    if not any(details.get(key) for key in ("from", "to", "on", "at")):
        raise OccupancyError("missing_time_detail")
    starts, ends = details.get("from", []), details.get("to", [])
    if bool(starts) != bool(ends) or len(starts) != len(ends):
        raise OccupancyError("incomplete_period")
    for key in ("from", "to"):
        normalized = []
        for value in details.get(key, []):
            if parse_datetime(value) is None:
                raise OccupancyError("invalid_time_value")
            normalized.append(instant(value, zone))
        details[key] = normalized
    for left, right in zip(details["from"], details["to"]):
        if right <= left:
            raise OccupancyError("invalid_span")
        if left < end and right > start:
            # Check transitions within the intersecting event, plus boundaries.
            constant_offset(left, right, zone)
            if (
                left.astimezone(timezone_info(zone)).utcoffset()
                != right.astimezone(timezone_info(zone)).utcoffset()
            ):
                raise OccupancyError("unsupported_timezone_window")
    for key in ("from", "to"):
        details[key] = [wall(value, zone).isoformat() for value in details[key]]
    on = details.get("on", [])
    if any(parse_date(value) is None for value in on):
        raise OccupancyError("invalid_time_value")
    at_values = []
    for value in details.get("at", []):
        if parse_datetime(value) is not None:
            points = [instant(value, zone)]
        elif parse_time(value) is not None:
            anchors = [parse_date(v) for v in on] if on else [date]
            points = [
                plain(interpret_time(value, anchor, zone)).astimezone(utc_timezone.utc)
                for anchor in anchors
            ]
        else:
            raise OccupancyError("invalid_time_value")
        if (
            item.kind == "E"
            and any(start <= point < end for point in points)
            and not starts
            and not on
        ):
            raise OccupancyError("unknown_duration")
        at_values.extend(wall(point, zone).isoformat() for point in points)
    details["at"] = at_values
    return Item(
        item.status, item.kind, item.title, details, line=item.line, source=item.source
    )


def occupancy(items, date, start, end, zone, limits, ref, diagnostic):
    """Return certified known freebusy data plus independent uncertainty flags."""
    normalized, originals, diagnostics = [], {}, []
    busy_items = [item for item in items if item.kind in ("E", "R")]
    if len(busy_items) > limits["events"]:
        return None, [diagnostic("limit_exceeded", effect="block")]
    # on x at can expand into many markers even without repeat. Bound that
    # product BEFORE normalization/anchoring, not after constructing all points.
    potential = sum(
        len(it.details.get("from", []))
        + len(it.details.get("on", []))
        + len(it.details.get("at", [])) * max(1, len(it.details.get("on", [])))
        for it in busy_items
    )
    if potential > limits["slots"]:
        return None, [diagnostic("limit_exceeded", effect="block")]
    for index, item in enumerate(busy_items):
        try:
            copy = normalized_event(item, date, start, end, zone)
            copy.source = str(index)
            normalized.append(copy)
            originals[(copy.source, copy.line)] = item
        except (OccupancyError, ValueError, OverflowError) as exc:
            code = (
                exc.code
                if isinstance(exc, OccupancyError)
                else "unsupported_timezone_window"
            )
            diagnostics.append(diagnostic(code, item, effect="block"))
    # Upper-bound every attendance match BEFORE legacy conflict enumeration.
    spans = sum(
        len(it.details.get("from", [])) + len(it.details.get("on", []))
        for it in normalized
    )
    points = sum(len(it.details.get("at", [])) for it in normalized)
    if (
        spans + points > limits["slots"]
        or spans * (spans - 1) // 2 > limits["conflicts"]
    ):
        return None, diagnostics + [diagnostic("limit_exceeded", effect="block")]
    result = compute_freebusy(normalized, wall(start, zone), wall(end, zone))
    for row in result["busy"] + result["instants"]:
        original = originals[(row["item"]["source"], row["item"]["line"])]
        row["item"] = ref(original)
    for conflict in result["conflicts"]:
        a = originals[(conflict["a"]["source"], conflict["a"]["line"])]
        b = originals[(conflict["b"]["source"], conflict["b"]["line"])]
        diagnostics.append(
            diagnostic(
                "conflict",
                effect="warning",
                a=ref(a),
                b=ref(b),
                start=conflict["start"],
                end=conflict["end"],
            )
        )
    return result, diagnostics
