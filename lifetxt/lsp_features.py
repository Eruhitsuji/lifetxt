"""Conservative editing context, with Core metadata as semantic authority."""

import re

from .completion import candidates, VALUE_KINDS
from .ids import collect_item_ids
from .interactive import TYPE_DESCRIPTIONS, STATUS_DESCRIPTIONS, DETAIL_DESCRIPTIONS
from .model import (
    VALID_STATUSES,
    VALID_TYPES,
    KNOWN_KEYS,
    REFERENCE_KEYS,
    RECOMMENDED_KEY_GROUPS,
    RECOMMENDED_KEYS_BY_TYPE,
    RECOMMENDED_KEYS_BY_STATUS,
)
from .lsp_document import MAX_RESULTS, utf16_length
from .safety_foundation import format_version_report

_TOKEN = re.compile(r'(?:[^\s"]|"(?:\\.|[^"\\])*")+')
_START = re.compile(r"^( *)(\[(?: |/|x|-|>|\?|N)\]) ([TEDRHNSMJ]) (.*)$")
_PEOPLE = {"owner", "assignee", "attendee", "sender", "recipient", "user", "person"}


def description(value):
    for code, name, text in (*TYPE_DESCRIPTIONS, *STATUS_DESCRIPTIONS):
        if value == code:
            return f"{code} — {name}: {text}"
    if value in DETAIL_DESCRIPTIONS:
        return f"{value}: {DETAIL_DESCRIPTIONS[value][0]}"
    if value in REFERENCE_KEYS:
        return f"{value}: Item ID reference."
    return f"{value}: Custom or additional detail key; preserved by Format 1.0."


def context(document, position):
    row, offset = document.offset(position)
    line = document.lines[row]
    prefix = line[:offset]
    if row == 0:
        prefix = prefix.removeprefix("\ufeff")
    indent = len(prefix) - len(prefix.lstrip(" "))
    stripped = prefix[indent:]
    if not stripped or (stripped.startswith("[") and "]" not in stripped):
        return "status", stripped, offset - len(stripped), None
    if stripped.startswith(("#", "|")):
        return None
    status = re.match(r"^(\[(?: |/|x|-|>|\?|N)\]) (\S*)$", stripped)
    if status:
        return "type", status[2], offset - len(status[2]), None
    # A physical continuation has no safely recoverable title boundary here.
    # Fail closed instead of offering edits in multiline/partial quoted text.
    if row and document.lines[row - 1].endswith("\\"):
        return None
    full = _START.match(prefix)
    if not full:
        return None
    rest = full[4]
    tokens = list(_TOKEN.finditer(rest))
    if not tokens or (len(tokens) == 1 and not rest.endswith(" ")):
        return None
    # Check quote/escape state rather than interpreting incomplete text as keys.
    quoted = escaped = False
    for char in rest:
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
    if quoted:
        return None
    current = "" if rest.endswith(" ") else tokens[-1][0]
    start = offset - len(current)
    if ":" in current:
        key, value = current.split(":", 1)
        if value.startswith('"') or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            return None
        return "value", value, start + len(key) + 1, key
    if not re.fullmatch(r"[a-z0-9_]*", current):
        return None
    return "key", current, start, (full[2], full[3])


def completion(document, position, items=None):
    ctx = context(document, position)
    if (
        ctx is None
        or format_version_report(document.text.removeprefix("\ufeff"))["state"]
        == "unsupported"
    ):
        return []
    kind, prefix, start, extra = ctx
    if kind == "status":
        values = VALID_STATUSES
    elif kind == "type":
        values = VALID_TYPES
    elif kind == "key":
        status, type_ = extra
        recommended = (
            *RECOMMENDED_KEYS_BY_TYPE.get(type_, ()),
            *RECOMMENDED_KEYS_BY_STATUS.get(status, ()),
        )
        pool = (
            *recommended,
            *KNOWN_KEYS,
            document.id_key,
            *REFERENCE_KEYS,
            *(k for _, keys in RECOMMENDED_KEY_GROUPS for k in keys),
            *(k for item in (items or document.result[0]) for k in item.details),
        )
        values = tuple(dict.fromkeys(pool))
    else:
        value_kind = (
            "id" if extra in REFERENCE_KEYS else "person" if extra in _PEOPLE else extra
        )
        if value_kind not in VALUE_KINDS or value_kind in ("type", "status", "key"):
            return []
        if value_kind == "id":
            values = sorted(
                v
                for v in collect_item_ids(
                    items if items is not None else document.result[0],
                    key=document.id_key,
                )
                if v.startswith(prefix)
            )[:MAX_RESULTS]
        else:
            values = candidates(
                value_kind,
                prefix=prefix,
                items=items if items is not None else document.result[0],
                limit=MAX_RESULTS,
            )
    row, offset = document.offset(position)
    line = document.lines[row]
    # Replace the complete current token when invoked in its middle.
    end = offset
    while end < len(line) and line[end] not in ' \t":':
        end += 1
    if kind == "key" and end < len(line) and line[end] == ":":
        end += 1
    if kind == "status" and "]" in line[offset:]:
        close = line.index("]", offset)
        if close - offset < 3:
            end = close + 1
    range_ = {
        "start": {"line": row, "character": utf16_length(line[:start])},
        "end": {"line": row, "character": utf16_length(line[:end])},
    }
    return [
        {
            "label": v + (":" if kind == "key" else ""),
            "kind": 10 if kind == "key" else 12,
            "sortText": f"{index:03}",
            "detail": description(v) if kind != "value" else extra,
            "textEdit": {
                "range": range_,
                "newText": v + ":"
                if kind == "key"
                else _quote(v)
                if kind == "value"
                else v,
            },
        }
        for index, v in enumerate(values)
        if v.startswith(prefix)
    ][:MAX_RESULTS]


def _quote(value):
    if any(c.isspace() or c in '"\\' for c in value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def hover(document, position):
    row, offset = document.offset(position)
    line = document.lines[row]
    if line.lstrip().startswith(("#", "|")):
        return None
    match = _START.match(line.removeprefix("\ufeff") if row == 0 else line)
    if not match:
        return None
    bom = 1 if row == 0 and line.startswith("\ufeff") else 0
    candidates_ = [
        (match.start(2) + bom, match.end(2) + bom, match[2]),
        (match.start(3) + bom, match.end(3) + bom, match[3]),
    ]
    # Only complete detail tokens after the title, never words inside values.
    rest = match[4]
    quoted = escaped = False
    for char in rest:
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
    if quoted:
        return None
    tokens = list(_TOKEN.finditer(rest))
    for token in tokens[1:]:
        key = token[0].split(":", 1)[0]
        if ":" in token[0] and re.fullmatch(r"[a-z][a-z0-9_]*", key):
            start = match.start(4) + token.start() + bom
            candidates_.append((start, start + len(key), key))
    for start, end, value in candidates_:
        if start <= offset < end:
            return {
                "contents": {"kind": "plaintext", "value": description(value)},
                "range": {
                    "start": {"line": row, "character": utf16_length(line[:start])},
                    "end": {"line": row, "character": utf16_length(line[:end])},
                },
            }
    return None
