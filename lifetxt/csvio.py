import csv
import io
import json
from collections import OrderedDict

from .model import Item, KNOWN_KEYS


FIXED_COLUMNS = ("status", "type", "title")
IGNORED_INPUT_COLUMNS = ("line", "source", "text")


def items_to_csv(items):
    columns = list(FIXED_COLUMNS) + _detail_columns(items)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for item in items:
        row = OrderedDict()
        row["status"] = item.status
        row["type"] = item.kind
        row["title"] = item.title
        for key in columns:
            if key in FIXED_COLUMNS:
                continue
            row[key] = _values_to_cell(item.details.get(key, []))
        writer.writerow(row)
    return output.getvalue()


def items_from_csv_text(text):
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    fields = list(reader.fieldnames)
    field_lookup = {field.lower(): field for field in fields if field is not None}
    status_field = field_lookup.get("status")
    type_field = field_lookup.get("type") or field_lookup.get("kind")
    title_field = field_lookup.get("title")
    if not status_field or not type_field or not title_field:
        raise ValueError("CSV input requires status, type, and title columns.")

    ignored = set(FIXED_COLUMNS) | set(IGNORED_INPUT_COLUMNS) | {"kind"}
    detail_fields = [
        field
        for field in fields
        if field
        and field.lower() not in ignored
    ]

    items = []
    for index, row in enumerate(reader, 2):
        if not _row_has_content(row):
            continue
        details = OrderedDict()
        for field in detail_fields:
            value = row.get(field)
            if value is None or value == "":
                continue
            details[field] = _cell_to_values(value)
        items.append(
            Item(
                row.get(status_field, ""),
                row.get(type_field, ""),
                row.get(title_field, ""),
                details,
                index,
            )
        )
    return items


def _detail_columns(items):
    seen = OrderedDict()
    for key in KNOWN_KEYS:
        seen[key] = None
    for item in items:
        for key in item.details.keys():
            seen.setdefault(key, None)

    columns = []
    used = set(FIXED_COLUMNS)
    for key in seen.keys():
        if key in used:
            continue
        if any(key in item.details for item in items):
            columns.append(key)
    return columns


def _values_to_cell(values):
    if not values:
        return ""
    if len(values) == 1:
        return str(values[0])
    return json.dumps([str(value) for value in values], ensure_ascii=False, separators=(",", ":"))


def _cell_to_values(value):
    text = str(value)
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            decoded = json.loads(stripped)
        except ValueError:
            return [text]
        if isinstance(decoded, list):
            return [str(entry) for entry in decoded]
    return [text]


def _row_has_content(row):
    for value in row.values():
        if value not in (None, ""):
            return True
    return False
