import re
from collections import OrderedDict, namedtuple
from datetime import datetime, timedelta, timezone

from .model import Item


Property = namedtuple("Property", "name params value")

_DATE_RE = re.compile(r"^\d{8}$")
_DATETIME_RE = re.compile(r"^\d{8}T\d{4}(\d{2})?Z?$")


def items_from_ics_text(text, project=None, tags=None):
    """Convert VEVENT components in iCalendar text to life.txt event items."""

    items = []
    for event in _parse_vevents(text):
        items.append(_event_to_item(event, project=project, tags=tags or []))
    return items


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
