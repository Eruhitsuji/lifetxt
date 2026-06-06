import json
import re
from collections import OrderedDict
from datetime import date, datetime, time, timedelta

from .serializer import item_to_line


_DATE_FORMAT = "%Y-%m-%d"
_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
_TIME_FORMAT = "%H:%M"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_DURATION_RE = re.compile(r"^(\d+)([mhd]?)$")

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
        raise ValueError("Duration must look like 30m, 2h, or 1d.")
    amount = int(match.group(1))
    unit = match.group(2) or "m"
    if unit == "m":
        return timedelta(minutes=amount)
    if unit == "h":
        return timedelta(hours=amount)
    if unit == "d":
        return timedelta(days=amount)
    raise ValueError("Unsupported duration unit %r." % unit)


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
        record["text"] = item_to_line(item)
        records.append(record)
    records.sort(key=_record_sort_key)
    return records


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
        candidate_dates = on_dates if on_dates else _range_dates(range_start, range_end)
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
