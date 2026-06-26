import json
import os
import sys
from collections import OrderedDict
from datetime import datetime

from .config import config_section
from .ids import id_key_from_config
from .parser import parse_text
from .serializer import item_to_line
from .timeutil import format_elapsed, parse_date, parse_date_or_datetime, parse_elapsed


DEFAULT_STATE_FILE = "~/.lifetxt_timer.json"


def cmd_timer(args):
    command = args.timer_command
    if command == "start":
        return start_timer(args)
    if command == "pause":
        return pause_timer(args)
    if command == "resume":
        return resume_timer(args)
    if command == "stop":
        return stop_timer(args)
    if command == "status":
        return status_timer(args)
    if command == "summary":
        return summary_timer(args)
    if command == "cancel":
        return cancel_timer(args)
    raise ValueError("timer requires start, pause, resume, stop, status, summary, or cancel.")


def start_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    if os.path.exists(state_file):
        raise ValueError("A timer is already running. Use `lifetxt timer status` or `lifetxt timer stop` first.")
    item = find_item_in_file(args.path, args.item_id, _id_key(args))
    now = _now()
    state = OrderedDict(
        [
            ("id", args.item_id),
            ("file", args.path),
            ("started_at", format_datetime(now)),
            ("accumulated_minutes", 0),
            ("paused_at", ""),
            ("note", args.note or ""),
        ]
    )
    _write_json(state_file, state)
    if item.status == "[ ]":
        update_item_in_file(args.path, args.item_id, _id_key(args), status="[/]")
    sys.stdout.write("Started timer for %s (%s) at %s\n" % (args.item_id, item.title, format_datetime(now)))
    return 0


def stop_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    state = _read_state(state_file)
    item_id = args.item_id or state.get("id")
    if args.item_id and args.item_id != state.get("id"):
        raise ValueError("Running timer is for %s, not %s." % (state.get("id"), args.item_id))
    path = args.path or state.get("file")
    minutes = state_elapsed_minutes(state, _now())
    item = find_item_in_file(path, item_id, _id_key(args))
    existing = 0
    for value in item.details.get("elapsed", []):
        existing += parse_elapsed(value)
    total = existing + minutes
    updated_line = update_item_in_file(path, item_id, _id_key(args), set_details={"elapsed": [format_elapsed(total)]})
    os.remove(state_file)
    sys.stdout.write("Stopped timer for %s (%s): +%s total %s\n" % (item_id, item.title, format_elapsed(minutes), format_elapsed(total)))
    sys.stdout.write(updated_line + "\n")
    return 0


def pause_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    state = _read_state(state_file)
    if state.get("paused_at"):
        raise ValueError("Timer is already paused.")
    now = _now()
    minutes = state_elapsed_minutes(state, now)
    state["accumulated_minutes"] = minutes
    state["paused_at"] = format_datetime(now)
    _write_json(state_file, state)
    sys.stdout.write("Paused timer for %s: elapsed %s\n" % (state.get("id"), format_elapsed(minutes)))
    return 0


def resume_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    state = _read_state(state_file)
    if not state.get("paused_at"):
        raise ValueError("Timer is not paused.")
    now = _now()
    state["started_at"] = format_datetime(now)
    state["paused_at"] = ""
    _write_json(state_file, state)
    sys.stdout.write("Resumed timer for %s at %s\n" % (state.get("id"), format_datetime(now)))
    return 0


def status_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    if not os.path.exists(state_file):
        sys.stdout.write("No running timer.\n")
        return 0
    state = _read_state(state_file)
    minutes = state_elapsed_minutes(state, _now())
    title = ""
    path = state.get("file")
    item_id = state.get("id")
    try:
        item = find_item_in_paths(args.paths or [path], item_id, _id_key(args))
        title = item.title
    except ValueError:
        title = "unknown"
    if state.get("paused_at"):
        sys.stdout.write(
            "Paused: %s (%s)  elapsed: %s  paused: %s\n"
            % (item_id, title, format_elapsed(minutes), state.get("paused_at", ""))
        )
    else:
        sys.stdout.write(
            "Running: %s (%s)  elapsed: %s  started: %s\n"
            % (item_id, title, format_elapsed(minutes), state.get("started_at", ""))
        )
    return 0


def summary_timer(args):
    items = load_items(args.paths)
    start = _parse_date_boundary(args.start, is_end=False)
    end = _parse_date_boundary(args.end, is_end=True)
    rows = []
    total = 0
    by_project = OrderedDict()
    for item in items:
        if args.project and args.project not in item.details.get("project", []):
            continue
        if not _item_in_range(item, start, end):
            continue
        minutes = sum(parse_elapsed(value) for value in item.details.get("elapsed", []))
        if minutes <= 0:
            continue
        total += minutes
        project = item.details.get("project", [""])[0] if item.details.get("project") else ""
        by_project[project] = by_project.get(project, 0) + minutes
        rows.append(
            OrderedDict(
                [
                    ("id", _first(item.details.get(_id_key(args))) or ""),
                    ("title", item.title),
                    ("elapsed", format_elapsed(minutes)),
                    ("minutes", minutes),
                    ("project", project),
                ]
            )
        )
    if args.format == "json":
        data = OrderedDict(
            [
                ("total_minutes", total),
                ("total", format_elapsed(total)),
                ("items", rows),
                ("by_project", OrderedDict((key, {"minutes": value, "elapsed": format_elapsed(value)}) for key, value in by_project.items())),
            ]
        )
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_summary(rows, total, by_project, args.start, args.end))
    return 0


def cancel_timer(args):
    state_file = timer_state_file(getattr(args, "config_data", None))
    if os.path.exists(state_file):
        os.remove(state_file)
        sys.stdout.write("Canceled running timer.\n")
    else:
        sys.stdout.write("No running timer.\n")
    return 0


def timer_state_file(config):
    timer = config_section(config or {}, "timer")
    value = timer.get("state_file") or DEFAULT_STATE_FILE
    return os.path.abspath(os.path.expanduser(str(value)))


def elapsed_minutes(start, end):
    seconds = max(0, int((end - start).total_seconds()))
    return int((seconds + 59) // 60)


def state_elapsed_minutes(state, now):
    accumulated = _int_value(state.get("accumulated_minutes"))
    if state.get("paused_at"):
        return accumulated
    started_at = parse_datetime_value(state.get("started_at"))
    if started_at is None:
        raise ValueError("Timer state has an invalid started_at value.")
    return accumulated + elapsed_minutes(started_at, now)


def _int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_summary(rows, total, by_project, start, end):
    lines = []
    if start or end:
        lines.append("Date range: %s - %s" % (start or "", end or ""))
        lines.append("")
    if not rows:
        lines.append("No elapsed time found.")
    else:
        width_id = max([len("id")] + [len(row["id"]) for row in rows])
        width_title = max([len("title")] + [len(row["title"]) for row in rows])
        for row in rows:
            lines.append(
                "%s  %s  %8s  project:%s"
                % (
                    row["id"].ljust(width_id),
                    row["title"].ljust(width_title),
                    row["elapsed"],
                    row["project"],
                )
            )
        lines.append("-" * 50)
        lines.append("%s  %s" % ("Total".ljust(width_id + width_title + 2), format_elapsed(total)))
    if by_project:
        lines.append("")
        lines.append("By project:")
        for project, minutes in by_project.items():
            label = project or "(none)"
            lines.append("  %-12s %s" % (label, format_elapsed(minutes)))
    return "\n".join(lines).rstrip() + "\n"


def find_item_in_paths(paths, item_id, key):
    for path in paths:
        try:
            return find_item_in_file(path, item_id, key)
        except ValueError:
            continue
    raise ValueError("No item found with %s:%s." % (key, item_id))


def find_item_in_file(path, item_id, key):
    items, diagnostics = parse_text(_read_text(path), id_key=key)
    _raise_on_errors(diagnostics)
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if not matches:
        raise ValueError("No item found with %s:%s in %s." % (key, item_id, path))
    if len(matches) > 1:
        raise ValueError("Multiple items found with %s:%s in %s." % (key, item_id, path))
    return matches[0]


def update_item_in_file(path, item_id, key, status=None, set_details=None):
    text = _read_text(path)
    lines = text.splitlines(True)
    items, diagnostics = parse_text(text, id_key=key)
    _raise_on_errors(diagnostics)
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if not matches:
        raise ValueError("No item found with %s:%s in %s." % (key, item_id, path))
    if len(matches) > 1:
        raise ValueError("Multiple items found with %s:%s in %s." % (key, item_id, path))
    item = matches[0]
    if status is not None:
        item.status = status
    for detail_key, values in (set_details or {}).items():
        item.details[detail_key] = list(values)
    updated = item_to_line(item)
    start = item.line - 1
    end = getattr(item, "end_line", item.line) or item.line
    ending = _line_ending(lines[end - 1]) if lines else "\n"
    replacement = (updated + ending).splitlines(True)
    lines[start:end] = replacement
    _write_text(path, "".join(lines))
    return updated


def load_items(paths):
    items = []
    for path in paths:
        path_items, diagnostics = parse_text(_read_text(path))
        _raise_on_errors(diagnostics)
        items.extend(path_items)
    return items


def _item_in_range(item, start, end):
    if start is None and end is None:
        return True
    values = []
    for key in ("done", "on", "due", "do", "from", "created", "updated"):
        values.extend(item.details.get(key, []))
    for value in values:
        parsed = parse_date_or_datetime(value, is_end=False)
        if parsed is None:
            continue
        if start is not None and parsed < start:
            continue
        if end is not None and parsed > end:
            continue
        return True
    return False


def _parse_date_boundary(value, is_end=False):
    if not value:
        return None
    parsed = parse_date_or_datetime(value, is_end=is_end)
    if parsed is None:
        raise ValueError("Expected DATE or DATETIME: %s" % value)
    return parsed


def parse_datetime_value(value):
    if not value:
        return None
    parsed = parse_date_or_datetime(value, is_end=False)
    return parsed


def format_datetime(value):
    return value.replace(microsecond=0).isoformat()


def _now():
    return datetime.now().replace(microsecond=0)


def _read_state(path):
    if not os.path.exists(path):
        raise ValueError("No running timer.")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def _write_json(path, data):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _read_text(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _line_ending(line):
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\r"):
        return "\r"
    return "\n"


def _raise_on_errors(diagnostics):
    errors = [diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())


def _id_key(args):
    return id_key_from_config(getattr(args, "config_data", None) or {})


def _first(values):
    if values:
        return values[0]
    return None
