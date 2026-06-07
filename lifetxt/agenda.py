import json
import re
from collections import OrderedDict
from datetime import datetime, time, timedelta

from .model import (
    VALID_STATUSES,
    VALID_TYPES,
    normalize_status,
    normalize_type,
)
from .serializer import item_to_line


OPEN_STATUSES = ("[ ]", "[/]", "[>]", "[?]")
_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
_TIME_FORMAT = "%H:%M"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DURATION_RE = re.compile(r"^(\d+)([a-z]*)$")

_POINT_KEYS = ("due", "do", "moved_to")
_TABLE_COLUMNS = (
    ("when", "when"),
    ("key", "key"),
    ("line_text", "line"),
    ("type", "type"),
    ("status", "status"),
    ("title", "title"),
)


def parse_agenda_range(
    start_text=None,
    end_text=None,
    around_text=None,
    window_text="1h",
    now=None,
):
    """Parse CLI range options into inclusive start/end datetimes."""
    if now is None:
        now = datetime.now().replace(second=0, microsecond=0)

    if (start_text or end_text) and around_text:
        raise ValueError("Use either --from/--to or --around, not both.")
    if start_text or end_text:
        if not (start_text and end_text):
            raise ValueError("--from and --to must be used together.")
        start = _parse_range_boundary(start_text, is_end=False, now=now)
        end = _parse_range_boundary(end_text, is_end=True, now=now)
    else:
        center = _parse_around_value(around_text or "now", now)
        window = parse_duration(window_text)
        start = center - window
        end = center + window

    if end < start:
        raise ValueError("Range end must not be earlier than range start.")
    return start, end


def parse_duration(value):
    text = str(value or "").strip().lower()
    match = _DURATION_RE.match(text)
    if not match:
        raise ValueError("Duration must look like 30m, 2h, 1d, 1w, 1mo, or 1y.")
    amount = int(match.group(1))
    unit = match.group(2) or "m"
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return timedelta(seconds=amount)
    if unit in ("m", "min", "mins", "minute", "minutes"):
        return timedelta(minutes=amount)
    if unit in ("h", "hr", "hrs", "hour", "hours"):
        return timedelta(hours=amount)
    if unit in ("d", "day", "days"):
        return timedelta(days=amount)
    if unit in ("w", "week", "weeks"):
        return timedelta(weeks=amount)
    if unit in ("mo", "mon", "month", "months"):
        return timedelta(days=30 * amount)
    if unit in ("y", "yr", "yrs", "year", "years"):
        return timedelta(days=365 * amount)
    raise ValueError("Unsupported duration unit %r." % unit)


def parse_optional_time_range(after_text=None, before_text=None, now=None):
    if now is None:
        now = datetime.now().replace(second=0, microsecond=0)
    range_start = None
    range_end = None
    if after_text:
        range_start = _parse_range_boundary(after_text, is_end=False, now=now)
    if before_text:
        range_end = _parse_range_boundary(before_text, is_end=True, now=now)
    if range_start and range_end and range_end < range_start:
        raise ValueError("Time filter end must not be earlier than start.")
    return range_start, range_end


def agenda_records(items, range_start, range_end):
    records = []
    for item in items:
        matches = item_time_matches(item, range_start, range_end)
        if not matches:
            continue
        primary = matches[0]
        record = OrderedDict()
        record["when"] = format_match_time(primary)
        record["key"] = primary["key"]
        if item.line is not None:
            record["line"] = item.line
        record["status"] = item.status
        record["type"] = item.kind
        record["title"] = item.title
        record["matches"] = matches
        record["details"] = _copy_details(item.details)
        record["text"] = _item_line_text(item)
        records.append(record)
    records.sort(key=_record_sort_key)
    return records


def filter_items(
    items,
    open_only=False,
    statuses=None,
    kinds=None,
    projects=None,
    tags=None,
    persons=None,
    owners=None,
    assignees=None,
    attendees=None,
    detail_filters=None,
    text=None,
    range_start=None,
    range_end=None,
):
    statuses = _normalize_status_filter(statuses)
    kinds = _normalize_type_filter(kinds)
    projects = _normalize_filter_values(projects)
    tags = _normalize_filter_values(tags)
    persons = _normalize_filter_values(persons)
    owners = _normalize_filter_values(owners)
    assignees = _normalize_filter_values(assignees)
    attendees = _normalize_filter_values(attendees)
    details = _parse_detail_filters(detail_filters)
    text = text.lower() if text else None

    if range_start is None and range_end is not None:
        range_start = datetime.min
    if range_start is not None and range_end is None:
        range_end = datetime.max

    filtered = []
    for item in items:
        if open_only and item.status not in OPEN_STATUSES:
            continue
        if statuses and item.status not in statuses:
            continue
        if kinds and item.kind not in kinds:
            continue
        if projects and not _item_has_any_detail(item, "project", projects):
            continue
        if tags and not _item_has_any_detail(item, "tag", tags):
            continue
        if persons and not _item_has_any_detail(item, "person", persons):
            continue
        if owners and not _item_has_any_detail(item, "owner", owners):
            continue
        if assignees and not _item_has_any_detail(item, "assignee", assignees):
            continue
        if attendees and not _item_has_any_detail(item, "attendee", attendees):
            continue
        if details and not _item_matches_detail_filters(item, details):
            continue
        if text and text not in _item_search_text(item).lower():
            continue
        if range_start is not None and not item_time_matches(item, range_start, range_end):
            continue
        filtered.append(item)
    return filtered


def filter_agenda_records(
    records,
    open_only=False,
    statuses=None,
    kinds=None,
    projects=None,
    tags=None,
    persons=None,
    owners=None,
    assignees=None,
    attendees=None,
    detail_filters=None,
    text=None,
):
    statuses = _normalize_status_filter(statuses)
    kinds = _normalize_type_filter(kinds)
    projects = _normalize_filter_values(projects)
    tags = _normalize_filter_values(tags)
    persons = _normalize_filter_values(persons)
    owners = _normalize_filter_values(owners)
    assignees = _normalize_filter_values(assignees)
    attendees = _normalize_filter_values(attendees)
    details = _parse_detail_filters(detail_filters)
    text = text.lower() if text else None

    filtered = []
    for record in records:
        if open_only and record["status"] not in OPEN_STATUSES:
            continue
        if statuses and record["status"] not in statuses:
            continue
        if kinds and record["type"] not in kinds:
            continue
        if projects and not _record_has_any_detail(record, "project", projects):
            continue
        if tags and not _record_has_any_detail(record, "tag", tags):
            continue
        if persons and not _record_has_any_detail(record, "person", persons):
            continue
        if owners and not _record_has_any_detail(record, "owner", owners):
            continue
        if assignees and not _record_has_any_detail(record, "assignee", assignees):
            continue
        if attendees and not _record_has_any_detail(record, "attendee", attendees):
            continue
        if details and not _record_matches_detail_filters(record, details):
            continue
        if text and text not in _record_search_text(record).lower():
            continue
        filtered.append(record)
    return filtered


def item_time_matches(item, range_start, range_end):
    matches = []
    _add_from_to_matches(matches, item, range_start, range_end)
    _add_point_key_matches(matches, item, range_start, range_end)
    _add_at_matches(matches, item, range_start, range_end)
    _add_on_matches(matches, item, range_start, range_end)
    matches.sort(key=_match_sort_key)
    return matches


def format_agenda_table(records):
    if not records:
        return "No agenda items found.\n"

    rows = []
    for record in records:
        row = OrderedDict()
        for key, _heading in _TABLE_COLUMNS:
            if key == "line_text":
                value = record.get("line", "")
            else:
                value = record.get(key, "")
            row[key] = _table_cell(value)
        rows.append(row)

    widths = []
    for key, heading in _TABLE_COLUMNS:
        width = len(heading)
        for row in rows:
            width = max(width, len(row[key]))
        widths.append(width)

    lines = []
    lines.append(_format_table_row([heading for _key, heading in _TABLE_COLUMNS], widths))
    lines.append(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(
            _format_table_row(
                [row[key] for key, _heading in _TABLE_COLUMNS],
                widths,
            )
        )
    return "\n".join(lines) + "\n"


def agenda_records_to_json(records, pretty=False):
    indent = 2 if pretty else None
    return json.dumps(
        records,
        ensure_ascii=False,
        indent=indent,
        separators=None if pretty else (",", ":"),
    )


def agenda_records_to_jsonl(records):
    lines = []
    for record in records:
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    return "\n".join(lines)


def agenda_records_to_life(records):
    return "\n".join([record["text"] for record in records])


def format_range_label(range_start, range_end):
    return "%s..%s" % (_format_datetime(range_start), _format_datetime(range_end))


def _add_from_to_matches(matches, item, range_start, range_end):
    starts = item.details.get("from", [])
    ends = item.details.get("to", [])
    for index, start_text in enumerate(starts):
        start = _parse_datetime_value(start_text)
        if start is None:
            continue
        end = None
        if index < len(ends):
            end = _parse_datetime_value(ends[index])
        elif len(ends) == 1:
            end = _parse_datetime_value(ends[0])
        if end is None and item.kind != "S":
            end = start
        key = "from/to" if end and end != start else "from"
        _add_match(matches, key, start, end, range_start, range_end)

    if starts:
        return

    for end_text in ends:
        end = _parse_datetime_value(end_text)
        if end is not None:
            _add_match(matches, "to", end, end, range_start, range_end)


def _add_point_key_matches(matches, item, range_start, range_end):
    for key in _POINT_KEYS:
        for value in item.details.get(key, []):
            span = _parse_date_or_datetime_span(value)
            if span is not None:
                _add_match(matches, key, span[0], span[1], range_start, range_end)


def _add_at_matches(matches, item, range_start, range_end):
    at_values = item.details.get("at", [])
    if not at_values:
        return

    on_dates = _item_on_dates(item)
    for value in at_values:
        point = _parse_datetime_value(value)
        if point is not None:
            _add_match(matches, "at", point, point, range_start, range_end)
            continue

        at_time = _parse_time_value(value)
        if at_time is None:
            continue
        if on_dates:
            candidate_dates = on_dates
        elif _is_unbounded_range(range_start, range_end):
            continue
        elif (range_end.date() - range_start.date()).days > 366:
            candidate_dates = [_first_matching_date_for_time(range_start, at_time)]
        else:
            candidate_dates = _range_dates(range_start, range_end)
        for candidate_date in candidate_dates:
            point = datetime.combine(candidate_date, at_time)
            _add_match(matches, "at", point, point, range_start, range_end)


def _add_on_matches(matches, item, range_start, range_end):
    for value in item.details.get("on", []):
        span = _parse_date_span(value)
        if span is not None:
            _add_match(matches, "on", span[0], span[1], range_start, range_end)


def _add_match(matches, key, start, end, range_start, range_end):
    if start is None:
        return
    if _overlaps(start, end, range_start, range_end):
        match = OrderedDict()
        match["key"] = key
        match["start"] = _format_datetime(start)
        if end is not None and end != start:
            match["end"] = _format_datetime(end)
        elif end is None:
            match["end"] = ""
        matches.append(match)


def _overlaps(start, end, range_start, range_end):
    if end is None:
        return start <= range_end
    return start <= range_end and end >= range_start


def _is_unbounded_range(range_start, range_end):
    return range_start == datetime.min or range_end == datetime.max


def _parse_range_boundary(value, is_end, now):
    if str(value).strip().lower() == "now":
        return now
    if _DATE_RE.match(value):
        parsed = datetime.strptime(value, _DATE_FORMAT).date()
        if is_end:
            return datetime.combine(parsed, time(23, 59))
        return datetime.combine(parsed, time(0, 0))
    parsed = _parse_datetime_value(value)
    if parsed is None:
        raise ValueError("Datetime must be now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.")
    return parsed


def _parse_around_value(value, now):
    if str(value).strip().lower() == "now":
        return now
    if _DATE_RE.match(value):
        return datetime.combine(datetime.strptime(value, _DATE_FORMAT).date(), time(12, 0))
    parsed = _parse_datetime_value(value)
    if parsed is None:
        raise ValueError("--around must be now, YYYY-MM-DD, or YYYY-MM-DDTHH:MM.")
    return parsed


def _parse_date_or_datetime_span(value):
    point = _parse_datetime_value(value)
    if point is not None:
        return point, point
    return _parse_date_span(value)


def _parse_date_span(value):
    if not _DATE_RE.match(value):
        return None
    try:
        parsed = datetime.strptime(value, _DATE_FORMAT).date()
    except ValueError:
        return None
    return datetime.combine(parsed, time(0, 0)), datetime.combine(parsed, time(23, 59))


def _parse_datetime_value(value):
    if not _DATETIME_RE.match(value):
        return None
    try:
        return datetime.strptime(value, _DATETIME_FORMAT)
    except ValueError:
        return None


def _parse_time_value(value):
    if not _TIME_RE.match(value):
        return None
    try:
        return datetime.strptime(value, _TIME_FORMAT).time()
    except ValueError:
        return None


def _item_on_dates(item):
    dates = []
    for value in item.details.get("on", []):
        if not _DATE_RE.match(value):
            continue
        try:
            dates.append(datetime.strptime(value, _DATE_FORMAT).date())
        except ValueError:
            pass
    return dates


def _first_matching_date_for_time(range_start, at_time):
    candidate_date = range_start.date()
    point = datetime.combine(candidate_date, at_time)
    if point < range_start:
        candidate_date = candidate_date + timedelta(days=1)
    return candidate_date


def _range_dates(range_start, range_end):
    current = range_start.date()
    last = range_end.date()
    values = []
    while current <= last:
        values.append(current)
        current = current + timedelta(days=1)
    return values


def _match_sort_key(match):
    return (_parse_datetime_value(match["start"]) or datetime.max, match["key"])


def _record_sort_key(record):
    primary = record["matches"][0]
    start = _parse_datetime_value(primary["start"]) or datetime.max
    return (start, record.get("line", 0), record["type"], record["title"])


def format_match_time(match):
    if "end" in match and match["end"]:
        return "%s..%s" % (match["start"], match["end"])
    if "end" in match and match["end"] == "":
        return "%s.." % match["start"]
    return match["start"]


def _format_datetime(value):
    return value.strftime(_DATETIME_FORMAT)


def _copy_details(details):
    copied = OrderedDict()
    for key, values in details.items():
        copied[key] = list(values)
    return copied


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _table_cell(value):
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def _normalize_filter_values(values):
    normalized = []
    for raw in values or []:
        for value in str(raw).split(","):
            value = value.strip()
            if value and value not in normalized:
                normalized.append(value)
    return tuple(normalized)


def _normalize_status_filter(values):
    normalized = []
    for value in _normalize_filter_values(values):
        status = normalize_status(value)
        if status not in VALID_STATUSES:
            raise ValueError("Invalid status filter %r." % value)
        if status not in normalized:
            normalized.append(status)
    return tuple(normalized)


def _normalize_type_filter(values):
    normalized = []
    for value in _normalize_filter_values(values):
        kind = normalize_type(value)
        if kind not in VALID_TYPES:
            raise ValueError("Invalid type filter %r." % value)
        if kind not in normalized:
            normalized.append(kind)
    return tuple(normalized)


def _parse_detail_filters(values):
    filters = []
    for raw in values or []:
        text = str(raw).strip()
        if not text:
            continue
        if "=" in text:
            key, value = text.split("=", 1)
            filters.append((key.strip(), value.strip()))
        elif ":" in text:
            key, value = text.split(":", 1)
            filters.append((key.strip(), value.strip()))
        else:
            filters.append((text, None))
    return tuple(filters)


def _record_has_any_detail(record, key, values):
    details = record.get("details", {})
    record_values = details.get(key, [])
    if key == "person" and not record_values and record.get("type") == "S":
        record_values = ["self"]
    for value in values:
        if value in record_values:
            return True
    return False


def _item_has_any_detail(item, key, values):
    item_values = item.details.get(key, [])
    if key == "person" and not item_values and item.kind == "S":
        item_values = ["self"]
    for value in values:
        if value in item_values:
            return True
    return False


def _record_matches_detail_filters(record, filters):
    details = record.get("details", {})
    for key, value in filters:
        if not key:
            return False
        if key not in details:
            return False
        if value is not None and value not in details.get(key, []):
            return False
    return True


def _item_matches_detail_filters(item, filters):
    for key, value in filters:
        if not key:
            return False
        if key not in item.details:
            return False
        if value is not None and value not in item.details.get(key, []):
            return False
    return True


def _record_search_text(record):
    parts = [
        record.get("status", ""),
        record.get("type", ""),
        record.get("title", ""),
        record.get("text", ""),
    ]
    for values in record.get("details", {}).values():
        parts.extend(values)
    return " ".join(parts)


def _item_search_text(item):
    parts = [
        item.status,
        item.kind,
        item.title,
        _item_line_text(item),
        item_to_line(item),
    ]
    for values in item.details.values():
        parts.extend(values)
    return " ".join(parts)


def _item_line_text(item):
    if getattr(item, "source_text", None):
        return item.source_text
    return item_to_line(item)
