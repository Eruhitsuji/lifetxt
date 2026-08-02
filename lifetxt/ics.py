import re
from collections import OrderedDict, namedtuple
from datetime import datetime, timedelta, timezone

from .model import Item


Property = namedtuple("Property", "name params value")

_DATE_RE = re.compile(r"^\d{8}$")
_DATETIME_RE = re.compile(r"^\d{8}T\d{4}(\d{2})?Z?$")


def items_from_ics_text(
    text, project=None, tags=None, expand=False, expand_until=None, expand_count=None
):
    """Convert VEVENT components in iCalendar text to life.txt event items.

    By default a recurring event stays one record carrying `repeat:RRULE:...`,
    which is compact and keeps the rule authoritative. With ``expand`` each
    occurrence becomes its own record instead, which is what you want when the
    consumer cannot evaluate an RRULE, or when occurrences need to be
    completed, annotated, or rescheduled individually.
    """
    items = []
    for event in _parse_vevents(text):
        item = _event_to_item(event, project=project, tags=tags or [])
        if not expand:
            items.append(item)
            continue
        items.extend(
            _expanded_occurrences(item, event, until=expand_until, count=expand_count)
        )
    return items


#: How far ahead an unbounded rule is materialized when nothing else caps it.
DEFAULT_EXPAND_DAYS = 365
#: A hard ceiling so a daily rule cannot fill a file with tens of thousands
#: of records because a window was left wide.
MAX_EXPAND_OCCURRENCES = 500


def _expanded_occurrences(item, event=None, until=None, count=None):
    """One record per occurrence, or the original item when it does not repeat.

    Anything that cannot be expanded - no rule, an unsupported rule, a missing
    start - yields the original record unchanged rather than being dropped.
    Silently losing a calendar entry is far worse than leaving it compact.
    """
    from .recurrence import RecurrenceError, expand, rule_for_item

    try:
        rule = rule_for_item(item)
    except RecurrenceError:
        rule = None
    if rule is None:
        return [item]

    start = _series_start(item)
    if start is None:
        return [item]

    limit = count or rule.get("count") or MAX_EXPAND_OCCURRENCES
    limit = max(1, min(int(limit), MAX_EXPAND_OCCURRENCES))
    horizon = until
    if horizon is None and not rule.get("count"):
        horizon = start + timedelta(days=DEFAULT_EXPAND_DAYS)

    try:
        moments = list(expand(rule, start, before=horizon, limit=limit))
    except RecurrenceError:
        return [item]

    # A feed cancels a single occurrence with EXDATE. Materializing it anyway
    # would put an event on the calendar that the source already removed.
    excluded = _excluded_datetimes(event)
    if excluded:
        moments = [moment for moment in moments if moment not in excluded]

    if not moments:
        return [item]

    return [_occurrence_item(item, start, moment) for moment in moments]


def _excluded_datetimes(event):
    """EXDATE values as datetimes, matched against expanded occurrences.

    EXDATE may repeat and may list several comma-separated values, and an
    all-day series excludes whole dates rather than instants, so date-only
    entries are compared at midnight the way the expansion emits them.
    """
    if not event:
        return frozenset()

    excluded = set()
    for prop in _properties(event, "EXDATE"):
        for chunk in str(prop.value or "").split(","):
            text = chunk.strip()
            if not text:
                continue
            parsed = _parse_temporal_value(text)
            if parsed is not None:
                excluded.add(parsed)
    return frozenset(excluded)


def _parse_temporal_value(text):
    """A bare ICS DATE or DATE-TIME as a naive local datetime, or None."""
    value = text.strip()
    if value.endswith("Z"):
        try:
            moment = datetime.strptime(value, "%Y%m%dT%H%M%SZ")
        except ValueError:
            return None
        # Occurrences are emitted in local time, so UTC has to be converted
        # or an exclusion would silently fail to match.
        return moment.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    for pattern in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(value, pattern)
        except ValueError:
            continue
    return None


def _series_start(item):
    """The anchor date the rule counts from: `on:`, `from:`, `due:`, or `do:`."""
    from .timeutil import parse_date_or_datetime

    details = item.details or {}
    for key in ("on", "from", "due", "do"):
        values = details.get(key)
        if not values:
            continue
        raw = values[0] if isinstance(values, (list, tuple)) else values
        try:
            parsed = parse_date_or_datetime(str(raw))
        except Exception:
            continue
        if parsed is None:
            continue
        if isinstance(parsed, datetime):
            return parsed
        return datetime(parsed.year, parsed.month, parsed.day)
    return None


def _occurrence_item(item, series_start, moment):
    """A concrete record for one occurrence of a recurring event."""
    details = OrderedDict()
    timed = moment.hour or moment.minute or moment.second
    stamp = moment.strftime("%Y-%m-%dT%H:%M") if timed else moment.strftime("%Y-%m-%d")

    for key, values in (item.details or {}).items():
        if key == "repeat":
            # The instance is concrete; keeping the rule would make every
            # occurrence look like the head of its own series.
            continue
        if key == "id":
            # Occurrences share a UID, so the id needs the date to stay unique.
            base = values[0] if isinstance(values, (list, tuple)) else values
            details["id"] = ["%s_%s" % (base, moment.strftime("%Y%m%d"))]
            continue
        if key in ("on", "from", "due", "do"):
            details[key] = [stamp]
            continue
        details[key] = list(values) if isinstance(values, (list, tuple)) else [values]

    # `repeat_base` already means "the anchor this series counts from", so the
    # link back to the original event needs no new key.
    details["repeat_base"] = [series_start.strftime("%Y-%m-%d")]

    return Item(
        status=item.status,
        kind=item.kind,
        title=item.title,
        details=details,
        line=item.line,
    )


def _parse_vevents(text):
    events = []
    current = None
    for raw_line in _unfold_lines(text):
        parsed = _parse_property(raw_line)
        if parsed is None:
            continue
        name, params, value = parsed
        upper_value = value.upper()
        if name == "BEGIN" and upper_value == "VEVENT":
            current = []
            continue
        if name == "END" and upper_value == "VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is not None:
            current.append(Property(name, params, value))
    return events


def _unfold_lines(text):
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue
        if line[0] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _parse_property(line):
    if ":" not in line:
        return None
    head, value = line.split(":", 1)
    parts = _split_unquoted(head, ";")
    name = parts[0].strip().upper()
    if not name:
        return None
    params = OrderedDict()
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        params[key.strip().upper()] = _strip_param_quotes(raw_value.strip())
    return name, params, _unescape_text(value)


def _split_unquoted(text, separator):
    parts = []
    current = []
    in_quote = False
    for char in text:
        if char == '"':
            in_quote = not in_quote
            current.append(char)
            continue
        if char == separator and not in_quote:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    return parts


def _strip_param_quotes(value):
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def _unescape_text(value):
    result = []
    escaped = False
    for char in value:
        if escaped:
            if char in ("n", "N"):
                result.append(" ")
            elif char in ("\\", ";", ","):
                result.append(char)
            else:
                result.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        result.append(char)
    if escaped:
        result.append("\\")
    return _clean_text("".join(result))


def _clean_text(value):
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def _event_to_item(event, project=None, tags=None):
    uid = _first_value(event, "UID")
    title = _first_value(event, "SUMMARY") or uid or "Untitled_Event"
    status = _status_from_ics(_first_value(event, "STATUS"))
    details = OrderedDict()

    _add_detail(details, "id", uid)
    _add_detail(details, "source", "ics" if uid else None)
    _add_detail(details, "uid", uid)
    _add_event_time_details(details, event)
    _add_detail(details, "loc", _first_value(event, "LOCATION"))
    _add_detail(details, "note", _first_value(event, "DESCRIPTION"))
    _add_detail(details, "url", _first_value(event, "URL"))

    organizer = _first_property(event, "ORGANIZER")
    if organizer is not None:
        _add_detail(details, "owner", _person_value(organizer))

    for attendee in _properties(event, "ATTENDEE"):
        _add_detail(details, "attendee", _person_value(attendee))

    rrule = _first_value(event, "RRULE")
    if rrule:
        _add_detail(details, "repeat", "RRULE:" + rrule)

    for category in _categories(event):
        _add_detail(details, "tag", category)

    if project:
        _add_detail(details, "project", project)
    for tag in tags or []:
        _add_detail(details, "tag", tag)

    _add_detail(
        details,
        "created",
        _formatted_temporal_value(_first_property(event, "CREATED")),
    )
    _add_detail(
        details,
        "updated",
        _formatted_temporal_value(_first_property(event, "LAST-MODIFIED")),
    )
    if status == "[-]":
        _add_detail(details, "reason", "canceled")

    return Item(status, "E", title, details)


def _status_from_ics(value):
    value = (value or "").upper()
    if value == "CANCELLED":
        return "[-]"
    if value == "TENTATIVE":
        return "[?]"
    return "[ ]"


def _add_event_time_details(details, event):
    start = _first_property(event, "DTSTART")
    if start is None:
        return

    start_kind, start_value = _parse_temporal_property(start)
    if start_kind is None:
        return

    end = _first_property(event, "DTEND")
    if start_kind == "date":
        for value in _all_day_dates(start_value, end):
            _add_detail(details, "on", value)
        return

    _add_detail(details, "from", start_value)
    if end is None:
        return
    end_kind, end_value = _parse_temporal_property(end)
    if end_kind == "datetime":
        _add_detail(details, "to", end_value)


def _formatted_temporal_value(prop):
    if prop is None:
        return None
    _kind, value = _parse_temporal_property(prop)
    return value


def _parse_temporal_property(prop):
    value = prop.value.strip()
    if prop.params.get("VALUE", "").upper() == "DATE" or _DATE_RE.match(value):
        if not _DATE_RE.match(value):
            return None, None
        return "date", "%s-%s-%s" % (value[0:4], value[4:6], value[6:8])

    if not _DATETIME_RE.match(value):
        return None, None

    if value.endswith("Z"):
        fmt = "%Y%m%dT%H%MZ" if len(value) == 14 else "%Y%m%dT%H%M%SZ"
        utc_value = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        local_value = utc_value.astimezone().replace(tzinfo=None)
        return "datetime", _format_datetime(local_value)

    fmt = "%Y%m%dT%H%M" if len(value) == 13 else "%Y%m%dT%H%M%S"
    return "datetime", _format_datetime(datetime.strptime(value, fmt))


def _all_day_dates(start_value, end_prop):
    start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
    if end_prop is None:
        return [start_value]

    end_kind, end_value = _parse_temporal_property(end_prop)
    if end_kind != "date":
        return [start_value]

    end_date = datetime.strptime(end_value, "%Y-%m-%d").date()
    if end_date <= start_date:
        return [start_value]

    values = []
    current = start_date
    while current < end_date:
        values.append(current.isoformat())
        current += timedelta(days=1)
    return values


def _format_datetime(value):
    return value.strftime("%Y-%m-%dT%H:%M")


def _first_property(event, name):
    for prop in event:
        if prop.name == name:
            return prop
    return None


def _properties(event, name):
    return [prop for prop in event if prop.name == name]


def _first_value(event, name):
    prop = _first_property(event, name)
    if prop is None:
        return None
    return prop.value


def _person_value(prop):
    value = prop.params.get("CN") or prop.value
    if value.lower().startswith("mailto:"):
        value = value[7:]
    return value


def _categories(event):
    values = []
    for prop in _properties(event, "CATEGORIES"):
        for value in prop.value.split(","):
            value = value.strip()
            if value:
                values.append(value)
    return values


def _add_detail(details, key, value):
    if value is None:
        return
    value = _clean_text(value)
    if value == "":
        return
    details.setdefault(key, []).append(value)
