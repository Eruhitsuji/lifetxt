"""Query, navigation, and safe local action commands."""

import argparse
import calendar
import csv
import datetime

from .timezone_policy import today as timezone_today
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
from .nextaction import blocked_map, is_actionable
from .parser import parse_text
from .paths import expand_paths
from .serializer import item_to_line
from .timeutil import parse_elapsed
from .timeutil import relative_time

from .extra_common import *


def command_next(args, config_data):
    items = _load_items(args.paths, config_data)
    blockers = blocked_map(items)
    selected = []
    for item in items:
        if not is_actionable(
            item.status,
            item.details,
            blocked=bool(blockers.get(id(item))),
            kind=item.kind,
        ):
            continue
        if args.user and not _filter_user(item, args.user):
            continue
        if args.project and args.project not in _values(item, "project"):
            continue
        if args.context and args.context not in _values(item, "context"):
            continue
        selected.append(item)
    if args.rank:
        invalid_due = [
            item
            for item in selected
            if _first(item, "due") and _date_value(_first(item, "due")) is None
        ]
        if invalid_due:
            raise ValueError(
                "next --rank cannot rank items with an invalid due date: %s"
                % ", ".join(
                    "%s (due:%s)" % (_item_id(item) or item.title, _first(item, "due"))
                    for item in invalid_due
                )
            )
        today = timezone_today()
        selected.sort(key=lambda item: _rank_key(item, today))
    else:
        far_future = datetime.date.max
        selected.sort(
            key=lambda item: (
                _priority_key(_first(item, "priority")),
                _date_value(_first(item, "due")) or far_future,
                _date_value(_first(item, "created")) or far_future,
                item.line or 0,
            )
        )
    if args.limit:
        selected = selected[: args.limit]
    explanations = {}
    if args.why:
        today = timezone_today() if args.rank else None
        for item in selected:
            explanations[id(item)] = _next_action_explanation(item, args.rank, today)
    if args.format == "json":
        output_rows = []
        for item in selected:
            row = _item_record(item)
            if args.why:
                row["why"] = explanations[id(item)]
            output_rows.append(row)
        return _emit(
            _json_text(output_rows, args.pretty),
            args.output,
        )
    if args.format == "life":
        output = []
        for item in selected:
            output.append(item_to_line(item) + "\n")
            if args.why:
                output.append("Why: %s\n" % explanations[id(item)]["summary"])
        return _emit("".join(output), args.output)
    rows = [
        (
            _item_id(item) or "-",
            _first(item, "priority") or "-",
            _first(item, "due") or "-",
            _first(item, "project") or "-",
            item.title,
        )
        for item in selected
    ]
    output = _table(("ID", "PRI", "DUE", "PROJECT", "TITLE"), rows)
    if args.why:
        output += (
            "\n".join(
                "Why: %s: %s"
                % (_item_id(item) or item.title, explanations[id(item)]["summary"])
                for item in selected
            )
            + "\n"
        )
    return _emit(output, args.output)


def _next_action_explanation(item, rank=False, today=None):
    """Describe the deterministic eligibility and ordering evidence."""
    tags = [str(value).lstrip("#").lower() for value in _values(item, "tag")]
    priority = _first(item, "priority") or "(none)"
    due = _first(item, "due") or _first(item, "do") or "(none)"
    created = _first(item, "created") or "(none)"
    criteria = [
        "status %s is actionable" % item.status,
        "type %s is actionable" % item.kind,
        "no parked tags (%s)" % (", ".join(tags) if tags else "none"),
        "dependencies resolved",
    ]
    if rank:
        order = "overdue-aware rank"
        sort_key = list(_rank_key(item, today))
    else:
        order = "priority, due, created, line"
        sort_key = [
            _priority_key(priority),
            _date_value(due) or datetime.date.max,
            _date_value(created) or datetime.date.max,
            item.line or 0,
        ]
    sort_key = [
        value.isoformat() if isinstance(value, datetime.date) else value
        for value in sort_key
    ]
    return OrderedDict(
        (
            ("criteria", criteria),
            (
                "ordering",
                OrderedDict(
                    (
                        ("method", order),
                        ("priority", priority),
                        ("due", due),
                        ("created", created),
                        ("line", item.line),
                        ("sort_key", sort_key),
                    )
                ),
            ),
            (
                "summary",
                "%s; %s; %s; %s; ordered by %s"
                % (criteria[0], criteria[1], criteria[2], criteria[3], order),
            ),
        )
    )


def command_show(args, config_data):
    items = _load_items(args.paths, config_data)
    item = _find_item(items, args.id)
    if args.format == "json":
        return _emit(_json_text(_item_record(item), args.pretty), args.output)
    if args.format == "life":
        return _emit(item_to_line(item) + "\n", args.output)
    id_map = dict(
        (_item_id(candidate), candidate) for candidate in items if _item_id(candidate)
    )
    incoming = []
    for candidate in items:
        for key in ("parent", "ref", "depends_on", "blocks", "related"):
            if args.id in _values(candidate, key):
                incoming.append(
                    "%s:%s from %s"
                    % (key, _item_id(candidate) or candidate.title, candidate.source)
                )
    parent_chain = []
    seen = set()
    current = item
    while _first(current, "parent"):
        parent_id = _first(current, "parent")
        if parent_id in seen:
            parent_chain.append(parent_id + " (cycle)")
            break
        seen.add(parent_id)
        parent = id_map.get(parent_id)
        if parent is None:
            parent_chain.append(parent_id + " (missing)")
            break
        parent_chain.append("%s — %s" % (parent_id, parent.title))
        current = parent
    lines = [
        "%s %s %s" % (item.status, item.kind, item.title),
        "ID: %s" % (args.id,),
        "Source: %s:%s" % (item.source, item.line),
    ]
    if parent_chain:
        lines.append("Hierarchy: " + " <- ".join(parent_chain))
    if item.details:
        lines.append("Details:")
        for key, values in item.details.items():
            for value in values:
                relative = relative_time(value) if key in _DATE_DETAIL_KEYS else ""
                suffix = " (%s)" % relative if relative else ""
                lines.append("  %s: %s%s" % (key, value, suffix))
    if incoming:
        lines.append("Incoming links:")
        lines.extend("  " + value for value in incoming)
    return _emit("\n".join(lines) + "\n", args.output)


_DATE_DETAIL_KEYS = frozenset(
    ("due", "do", "from", "to", "on", "at", "created", "updated", "done")
)


def _resolve_editor(args, config_data):
    return (
        args.editor
        or str(config_data.get("editor") or "")
        or os.environ.get("VISUAL")
        or os.environ.get("EDITOR")
        or ("notepad" if os.name == "nt" else "vi")
    )


def _editor_command(editor, path, line):
    command = shlex.split(editor, posix=os.name != "nt")
    if not command:
        raise ValueError("Editor command is empty.")
    executable = os.path.basename(command[0]).lower()
    if executable in ("code", "code-insiders", "codium"):
        command.extend(("-g", "%s:%s" % (path, line)))
    elif executable in ("subl", "sublime_text"):
        command.append("%s:%s" % (path, line))
    elif executable in ("vim", "vi", "nvim", "nano", "emacs"):
        command.extend(("+%s" % line, path))
    else:
        command.append(path)
    return command


def command_edit(args, config_data):
    items = _load_items(args.paths, config_data, allow_stdin=False)
    item = _find_item(items, args.id)
    editor = _resolve_editor(args, config_data)
    command = _editor_command(editor, item.source, item.line or 1)
    if args.dry_run:
        sys.stdout.write(" ".join(shlex.quote(part) for part in command) + "\n")
        return 0
    from .editor_safety import safe_edit

    result = safe_edit(
        item.source,
        editor,
        line=item.line or 1,
        review_only=bool(getattr(args, "review_only", False)),
        reconcile=bool(getattr(args, "reconcile", False)),
        keep_temp=bool(getattr(args, "keep_temp", False)),
        operation="cli.edit",
    )
    if result.get("diff") and (
        getattr(args, "review_only", False) or getattr(args, "show_diff", False)
    ):
        sys.stdout.write(result["diff"])
    if result.get("temporary_path"):
        sys.stdout.write("Temporary edited copy: %s\n" % result["temporary_path"])
    if result.get("review_only"):
        sys.stdout.write("Review only; no changes were written.\n")
    elif result.get("written"):
        sys.stdout.write(
            "Applied editor changes with revision %s.\n" % result["after_revision"]
        )
    else:
        sys.stdout.write("Editor closed without changes.\n")
    return 0


def _default_notification_state_path(config_data):
    # Only the default is workspace-scoped; an explicitly configured
    # state_file (handled by the caller before falling back here) is left
    # exactly as the operator wrote it. Matches command_notify's own
    # resolution in cli.py so `lifetxt path` reports what `lifetxt notify
    # --watch` would actually use.
    from .workspace import workspace_scoped_default_path

    return workspace_scoped_default_path(
        ".cache/lifetxt/notifications.json", config_data
    )


def command_path(args, config_data, config_path):
    config_dir = (
        os.path.dirname(os.path.abspath(config_path)) if config_path else os.getcwd()
    )
    inputs = [
        _resolved_path(path, config_dir)
        for path in (config_paths(config_data) or ["life.txt"])
    ]
    timer = config_section(config_data, "timer")
    notifications = config_section(config_data, "notifications")
    data = OrderedDict(
        (
            (
                "config",
                _resolved_path(config_data.get("_path") or config_path)
                if (config_data.get("_path") or config_path)
                else None,
            ),
            ("inputs", inputs),
            (
                "write_file",
                _resolved_path(config_write_file(config_data) or inputs[0], config_dir),
            ),
            ("editor", str(config_data.get("editor") or "")),
            (
                "timer_state",
                _resolved_path(
                    timer.get("state_file") or "~/.lifetxt_timer.json", config_dir
                ),
            ),
            (
                "notification_state",
                _resolved_path(
                    notifications.get("state_file")
                    or _default_notification_state_path(config_data),
                    config_dir,
                ),
            ),
            ("cache_dir", _resolved_path(".cache/lifetxt", config_dir)),
        )
    )
    if args.format == "json":
        return _emit(_json_text(data, args.pretty))
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append("%s:" % key)
            lines.extend("  %s" % entry for entry in value)
        else:
            lines.append("%s: %s" % (key, value or "(not set)"))
    return _emit("\n".join(lines) + "\n")


def _group_values(item, group):
    if group == "status":
        return [item.status]
    if group == "type":
        return [item.kind]
    if group == "person":
        for key in ("assignee", "owner", "person", "user"):
            values = _values(item, key)
            if values:
                return values
        return []
    return _values(item, group)


def command_count(args, config_data):
    items = _load_items(args.paths, config_data)
    counts = {}
    for item in items:
        values = _group_values(item, args.by) or ["(none)"]
        for value in set(values):
            counts[value] = counts.get(value, 0) + 1
    rows = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].lower()))
    if args.format == "json":
        return _emit(_json_text(OrderedDict(rows), args.pretty), args.output)
    if args.format == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow((args.by, "count"))
        writer.writerows(rows)
        return _emit(stream.getvalue(), args.output)
    return _emit(_table((args.by.upper(), "COUNT"), rows), args.output)


def command_workload(args, config_data):
    items = _load_items(args.paths, config_data)
    today = timezone_today()
    cutoff = today + datetime.timedelta(days=args.due_soon_days)
    data = {}
    for item in items:
        if item.kind != "T" or item.status not in OPEN_STATUSES:
            continue
        people = _values(item, "assignee") or _values(item, "owner") or ["(unassigned)"]
        due = _date_value(_first(item, "due"))
        for person in set(people):
            bucket = data.setdefault(
                person, {"open": 0, "due_soon": 0, "overdue": 0, "in_progress": 0}
            )
            bucket["open"] += 1
            if item.status == "[/]":
                bucket["in_progress"] += 1
            if due is not None and due < today:
                bucket["overdue"] += 1
            elif due is not None and due <= cutoff:
                bucket["due_soon"] += 1
    ordered = OrderedDict((name, data[name]) for name in sorted(data))
    if args.format == "json":
        return _emit(_json_text(ordered, args.pretty))
    rows = [
        (
            name,
            values["open"],
            values["in_progress"],
            values["due_soon"],
            values["overdue"],
        )
        for name, values in ordered.items()
    ]
    return _emit(_table(("PERSON", "OPEN", "DOING", "DUE SOON", "OVERDUE"), rows))


def _attachment_value(value):
    marker = "#sha256="
    return value.split(marker, 1)[0] if marker in value else value


def _is_within(path, root):
    try:
        return os.path.commonpath(
            (os.path.realpath(path), os.path.realpath(root))
        ) == os.path.realpath(root)
    except ValueError:
        return False


def command_files_open(args, config_data):
    items = _load_items(args.paths, config_data, allow_stdin=False)
    item = _find_item(items, args.open_id)
    attachments = []
    for key in ("file", "dir"):
        for value in _values(item, key):
            attachments.append((key, value))
    if not attachments:
        raise ValueError("Item %s has no file: or dir: attachment." % args.open_id)
    if args.index < 1 or args.index > len(attachments):
        raise ValueError("--index must be between 1 and %s." % len(attachments))
    key, raw = attachments[args.index - 1]
    value = _attachment_value(raw)
    if "://" in value or "\x00" in value:
        raise ValueError("Only local filesystem attachments can be opened.")
    base = os.path.dirname(item.source)
    path = value if os.path.isabs(value) else os.path.join(base, value)
    path = os.path.abspath(os.path.expanduser(os.path.expandvars(path)))
    if not os.path.exists(path):
        raise ValueError("Attachment does not exist: %s" % path)
    if key == "file" and not os.path.isfile(path):
        raise ValueError("file: attachment is not a file: %s" % path)
    if key == "dir" and not os.path.isdir(path):
        raise ValueError("dir: attachment is not a directory: %s" % path)
    if not args.allow_outside and not _is_within(path, base):
        raise ValueError(
            "Attachment resolves outside the life.txt directory; pass --allow-outside to confirm."
        )
    extension = os.path.splitext(path)[1].lower()
    # os.access(X_OK) is meaningless on Windows: it reports True for any
    # readable file, which would block every attachment. There, the extension
    # blocklist above is the signal that actually distinguishes an executable.
    executable_bit = os.name != "nt" and os.access(path, os.X_OK)
    if (
        os.path.isfile(path)
        and not args.allow_unsafe
        and (extension in BLOCKED_OPENERS or executable_bit)
    ):
        raise ValueError(
            "Refusing to open a potentially executable attachment; pass --allow-unsafe to confirm."
        )
    if args.dry_run:
        sys.stdout.write(path + "\n")
        return 0
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return 0
    command = ["open", path] if sys.platform == "darwin" else ["xdg-open", path]
    return subprocess.call(command)


def command_someday(args, config_data):
    items = _load_items(args.paths, config_data)
    today = timezone_today()
    cutoff = today - datetime.timedelta(days=args.days)
    selected = []
    for item in items:
        if item.status != "[?]":
            continue
        touched = _latest_date(item, ("updated", "created", "do", "due", "on"))
        if touched is None or touched <= cutoff:
            selected.append(item)
    selected.sort(
        key=lambda item: (_latest_date(item) or datetime.date.min, item.title.lower())
    )
    if args.format == "json":
        return _emit(
            _json_text([_item_record(item) for item in selected], args.pretty),
            args.output,
        )
    if args.format == "life":
        return _emit(
            "".join(item_to_line(item) + "\n" for item in selected), args.output
        )
    rows = [
        (
            _item_id(item) or "-",
            (_latest_date(item) or datetime.date.min).isoformat()
            if _latest_date(item)
            else "unknown",
            _first(item, "project") or "-",
            item.title,
        )
        for item in selected
    ]
    return _emit(_table(("ID", "LAST TOUCHED", "PROJECT", "TITLE"), rows), args.output)
