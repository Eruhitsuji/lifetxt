import json
import re
from collections import OrderedDict

from .model import Item


_KEY_RE = re.compile(r'^[^ :"]+$')
_BARE_RE = re.compile(r'^[^ "\t\\]+$')


def item_to_line(item):
    parts = [item.status, item.kind, encode_string(item.title)]
    continuation_lines = []
    for key, values in item.details.items():
        if not _KEY_RE.match(key):
            raise ValueError("Invalid detail key %r." % key)
        if key == "body" and _has_multiline_value(values):
            if len(values) != 1:
                raise ValueError(
                    "Multiline body text requires exactly one body: value; "
                    "repeated body: values cannot be represented losslessly with | continuation lines."
                )
            continuation_lines.extend(_body_continuation_lines(values[0]))
            continue
        for value in values:
            parts.append("%s:%s" % (key, encode_string(value)))
    line = " ".join(parts)
    indent = " " * int(getattr(item, "indent", 0) or 0)
    line = indent + line
    if continuation_lines:
        return "\n".join([line] + [indent + value for value in continuation_lines])
    return line


def encode_string(value):
    if value is None:
        value = ""
    if not isinstance(value, str):
        value = str(value)
    if "\n" in value or "\r" in value:
        raise ValueError("life.txt strings cannot contain newlines.")
    if value != "" and _BARE_RE.match(value):
        return value
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def _has_multiline_value(values):
    for value in values:
        if value is None:
            continue
        text = str(value)
        if "\n" in text or "\r" in text:
            return True
    return False


def _body_continuation_lines(value):
    if value is None:
        value = ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines:
        return ["|"]
    result = []
    for line in lines:
        if line == "":
            result.append("|")
        else:
            result.append("| " + line)
    return result


def items_to_json(items, pretty=False):
    indent = 2 if pretty else None
    return json.dumps(
        [item.to_dict() for item in items],
        ensure_ascii=False,
        indent=indent,
        separators=None if pretty else (",", ":"),
    )


def items_to_jsonl(items):
    lines = []
    for item in items:
        lines.append(
            json.dumps(item.to_dict(), ensure_ascii=False, separators=(",", ":"))
        )
    return "\n".join(lines)


def item_from_dict(data, line=None):
    if not isinstance(data, dict):
        raise ValueError("JSON item must be an object.")

    status = data.get("status")
    kind = data.get("type", data.get("kind"))
    title = data.get("title")
    details = data.get("details", OrderedDict())

    if status is None:
        raise ValueError("JSON item is missing status.")
    if kind is None:
        raise ValueError("JSON item is missing type.")
    if title is None:
        raise ValueError("JSON item is missing title.")
    if details is None:
        details = OrderedDict()
    if not isinstance(details, dict):
        raise ValueError("JSON item details must be an object.")

    normalized = OrderedDict()
    for key, values in details.items():
        if isinstance(values, list):
            normalized[key] = values
        elif isinstance(values, tuple):
            normalized[key] = list(values)
        else:
            normalized[key] = [values]

    return Item(status, kind, title, normalized, line, indent=data.get("indent", 0))


def items_from_json_text(text):
    data = json.loads(text)
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError(
            "JSON input must be an item object, an item array, or {items:[...]}."
        )
    return [item_from_dict(entry, index + 1) for index, entry in enumerate(data)]


def items_from_jsonl_text(text):
    items = []
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        data = json.loads(line)
        items.append(item_from_dict(data, line_no))
    return items
