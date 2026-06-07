import json
from collections import OrderedDict
from datetime import datetime


_DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
_TABLE_COLUMNS = (
    ("person", "person"),
    ("state", "state"),
    ("active_text", "current"),
    ("from", "from"),
    ("to", "to"),
    ("title", "title"),
    ("service", "service"),
    ("visibility", "visibility"),
)


def latest_status_records(items, person=None, active_only=False):
    """Return the latest status / presence record for each person."""
    latest = {}
    for index, item in enumerate(items):
        if item.kind != "S":
            continue
        record = status_record(item)
        if active_only and not record["active"]:
            continue
        if person is not None and record["person"] != person:
            continue
        started_at = _parse_status_datetime(record["from"])
        if started_at is None:
            continue
        line_no = item.line if item.line is not None else 0
        key = record["person"]
        sort_key = (started_at, line_no, index)
        existing = latest.get(key)
        if existing is None or sort_key > existing[0]:
            latest[key] = (sort_key, record)

    records = [entry[1] for entry in latest.values()]
    records.sort(key=lambda record: record["person"])
    return records


def status_record(item):
    person = _first_detail(item, "person", "self")
    to_value = _first_detail(item, "to", "")

    record = OrderedDict()
    record["person"] = person
    record["state"] = _first_detail(item, "state", "")
    record["active"] = "to" not in item.details
    record["status"] = item.status
    record["title"] = item.title
    record["from"] = _first_detail(item, "from", "")
    record["to"] = to_value
    record["service"] = _first_detail(item, "service", "")
    record["visibility"] = _first_detail(item, "visibility", "")
    if item.line is not None:
        record["line"] = item.line
    record["details"] = _copy_details(item.details)
    return record


def format_status_table(records):
    if not records:
        return "No status items found.\n"

    rows = []
    for record in records:
        row = OrderedDict()
        for key, _heading in _TABLE_COLUMNS:
            if key == "active_text":
                value = "yes" if record["active"] else "no"
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
    headings = [_TABLE_COLUMNS[index][1] for index in range(len(_TABLE_COLUMNS))]
    lines.append(_format_table_row(headings, widths))
    lines.append(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        lines.append(
            _format_table_row(
                [row[key] for key, _heading in _TABLE_COLUMNS],
                widths,
            )
        )
    return "\n".join(lines) + "\n"


def status_records_to_json(records, pretty=False):
    indent = 2 if pretty else None
    return json.dumps(
        records,
        ensure_ascii=False,
        indent=indent,
        separators=None if pretty else (",", ":"),
    )


def status_records_to_jsonl(records):
    lines = []
    for record in records:
        lines.append(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(lines)


def _first_detail(item, key, default):
    values = item.details.get(key)
    if not values:
        return default
    return values[0]


def _copy_details(details):
    copied = OrderedDict()
    for key, values in details.items():
        copied[key] = list(values)
    return copied


def _parse_status_datetime(value):
    try:
        return datetime.strptime(value, _DATETIME_FORMAT)
    except (TypeError, ValueError):
        return None


def _format_table_row(values, widths):
    cells = []
    for index, value in enumerate(values):
        cells.append(str(value).ljust(widths[index]))
    return "| " + " | ".join(cells) + " |"


def _table_cell(value):
    if value is None:
        return ""
    return str(value).replace("|", "\\|")
