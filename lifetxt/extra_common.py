"""Shared helpers for extended lifetxt CLI commands."""

import argparse
import calendar
import csv
import datetime
import hashlib
import io
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unicodedata
from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .atomic import atomic_write_text
from .config import (
    config_paths,
    config_section,
    config_user_name,
    config_write_file,
    load_config,
)
from .model import Item
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_to_line
from .timeutil import parse_elapsed
from .workspace import resolve_workspace, workspace_resolution_active

OPEN_STATUSES = ("[ ]", "[/]")
CLOSED_STATUSES = ("[x]", "[-]", "[>]")
BLOCKED_OPENERS = frozenset(
    (
        ".app",
        ".bat",
        ".cmd",
        ".com",
        ".desktop",
        ".exe",
        ".jar",
        ".js",
        ".jse",
        ".lnk",
        ".msi",
        ".ps1",
        ".scr",
        ".sh",
        ".url",
        ".vbs",
        ".vbe",
        ".wsf",
    )
)

__all__ = [
    "OPEN_STATUSES",
    "CLOSED_STATUSES",
    "BLOCKED_OPENERS",
    "_first",
    "_values",
    "_item_id",
    "_parse_date",
    "_date_value",
    "_latest_date",
    "_load_config",
    "_resolved_input_paths",
    "_load_items",
    "_find_item",
    "_write_output",
    "_json_text",
    "_display_width",
    "_pad",
    "_table",
    "_blocked",
    "_priority_key",
    "_rank_key",
    "_item_record",
    "_filter_user",
    "_emit",
    "_resolved_path",
    "Item",
    "OrderedDict",
    "datetime",
    "os",
    "sys",
    "shlex",
    "subprocess",
    "tempfile",
    "json",
    "csv",
    "io",
    "math",
    "calendar",
    "hashlib",
    "re",
    "Decimal",
    "InvalidOperation",
    "ROUND_HALF_UP",
    "item_to_line",
    "parse_elapsed",
    "expand_paths",
    "config_paths",
    "config_section",
    "config_user_name",
    "config_write_file",
    "load_config",
    "atomic_write_text",
]


def _first(item, key, default=""):
    values = item.details.get(key, [])
    return str(values[0]) if values else default


def _values(item, key):
    return [str(value) for value in item.details.get(key, [])]


def _item_id(item):
    return _first(item, "id")


def _parse_date(value, label="date"):
    text = str(value or "")[:10]
    try:
        return datetime.datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Invalid %s %r. Use YYYY-MM-DD." % (label, value))


def _date_value(value):
    text = str(value or "")
    if len(text) < 10:
        return None
    try:
        return datetime.date(int(text[:4]), int(text[5:7]), int(text[8:10]))
    except (ValueError, IndexError):
        return None


def _latest_date(
    item, keys=("done", "updated", "to", "from", "on", "do", "due", "created")
):
    result = None
    for key in keys:
        for value in _values(item, key):
            parsed = _date_value(value)
            if parsed is not None and (result is None or parsed > result):
                result = parsed
    return result


def _load_config(config_path, workspace_name=None):
    """Load config and inject the active workspace's resolved runtime paths.

    Extended commands historically loaded the JSON document directly, bypassing
    the legacy CLI's named-workspace resolution.  Keep legacy top-level
    ``paths`` / ``write_file`` behavior unchanged, but when a configured default
    workspace or explicit workspace applies, expose the same resolved
    ``paths``/``write_file`` runtime view that ordinary CLI commands receive.
    """
    config_data = load_config(config_path)
    if not workspace_resolution_active(config_data, workspace_name):
        return config_data

    resolution = resolve_workspace(config_data, workspace_name)
    config_data["paths"] = list(resolution["input_paths"])
    if resolution["write_file"]:
        config_data["write_file"] = resolution["write_file"]
    if resolution["generated_paths"] and "generated_paths" not in config_data:
        config_data["generated_paths"] = list(resolution["generated_paths"])
    config_data["_active_workspace"] = resolution["name"]
    return config_data


def _resolved_input_paths(paths, config_data, default="life.txt"):
    selected = list(paths or [])
    if not selected:
        selected = config_paths(config_data) or [default]
    return expand_paths(selected)


def _load_items(paths, config_data, allow_stdin=True):
    selected = _resolved_input_paths(paths, config_data)
    items = []
    stdin_used = False
    for path in selected:
        if path == "-":
            if not allow_stdin:
                raise ValueError("This command requires a real source path, not stdin.")
            if stdin_used:
                continue
            text = sys.stdin.read()
            source = "-"
            stdin_used = True
        else:
            with open(path, "r", encoding="utf-8-sig", newline="") as handle:
                text = handle.read()
            source = os.path.abspath(path)
        parsed, diagnostics = parse_text(text)
        errors = [
            diagnostic
            for diagnostic in diagnostics
            if getattr(diagnostic, "severity", "") == "error"
        ]
        if errors:
            first_error = errors[0]
            message = (
                first_error.format()
                if hasattr(first_error, "format")
                else str(first_error)
            )
            raise ValueError(
                "Cannot use %s because it contains parse errors: %s" % (source, message)
            )
        for item in parsed:
            item.source = source
        items.extend(parsed)
    return items


def _find_item(items, item_id):
    matches = [item for item in items if item_id in _values(item, "id")]
    if not matches:
        raise ValueError("Item ID not found: %s" % item_id)
    if len(matches) > 1:
        locations = ["%s:%s" % (item.source, item.line) for item in matches]
        raise ValueError(
            "Item ID %s is duplicated at %s" % (item_id, ", ".join(locations))
        )
    return matches[0]


def _write_output(text, output=None, append=False):
    if output:
        if append:
            current = ""
            if os.path.exists(output):
                with open(output, "r", encoding="utf-8-sig", newline="") as handle:
                    current = handle.read()
            if current and not current.endswith("\n"):
                current += "\n"
            atomic_write_text(output, current + text)
        else:
            atomic_write_text(output, text)
    else:
        sys.stdout.write(text)


def _json_text(data, pretty=False):
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
        + "\n"
    )


def _display_width(value):
    total = 0
    for char in str(value):
        if unicodedata.combining(char):
            continue
        total += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return total


def _pad(value, width):
    text = str(value)
    return text + " " * max(0, width - _display_width(text))


def _table(headers, rows):
    rows = [[str(value) for value in row] for row in rows]
    widths = []
    for index, header in enumerate(headers):
        values = [str(header)] + [row[index] for row in rows]
        widths.append(max(_display_width(value) for value in values))
    lines = [
        "  ".join(_pad(header, widths[index]) for index, header in enumerate(headers))
    ]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend(
        "  ".join(_pad(row[index], widths[index]) for index in range(len(headers)))
        for row in rows
    )
    return "\n".join(lines) + "\n"


def _blocked(item, id_map):
    for dependency in _values(item, "depends_on"):
        target = id_map.get(dependency)
        if target is None or target.status not in CLOSED_STATUSES:
            return True
    return False


def _priority_key(value):
    text = str(value or "").strip().upper()
    if not text:
        return (3, 9999, "")
    if len(text) == 1 and "A" <= text <= "Z":
        return (0, ord(text) - ord("A"), text)
    try:
        return (1, int(text), text)
    except ValueError:
        return (2, 0, text)


def _rank_key(item, today):
    """Overdue-aware sort key for `next --rank`.

    Overdue (due date earlier than `today`) sorts first; ties fall back to
    next's existing default ordering (priority, due, created, line) via
    _priority_key/_date_value unchanged, so ranked and default output only
    ever differ by the leading overdue bucket.
    """
    far_future = datetime.date.max
    due = _date_value(_first(item, "due"))
    created = _date_value(_first(item, "created"))
    is_overdue = 0 if due is not None and due < today else 1
    return (
        is_overdue,
        _priority_key(_first(item, "priority")),
        due or far_future,
        created or far_future,
        item.line or 0,
    )


def _item_record(item):
    return OrderedDict(
        (
            ("id", _item_id(item)),
            ("status", item.status),
            ("type", item.kind),
            ("title", item.title),
            (
                "details",
                OrderedDict(
                    (key, list(values)) for key, values in item.details.items()
                ),
            ),
            ("source", item.source),
            ("line", item.line),
        )
    )


def _filter_user(item, user):
    if not user:
        return True
    values = []
    for key in ("assignee", "owner", "user", "person"):
        values.extend(_values(item, key))
    return user in values


def _emit(text, output=None):
    _write_output(text, output=output)
    return 0


def _resolved_path(value, base=None):
    if not value:
        return ""
    value = os.path.expandvars(os.path.expanduser(str(value)))
    if base and not os.path.isabs(value):
        value = os.path.join(base, value)
    return os.path.abspath(value)
