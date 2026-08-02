import json
import os
import sys
from collections import OrderedDict

from .atomic import atomic_write_json, atomic_write_text
from . import mutation
from .mutation import MISSING_HASH
from .multi_target import (
    apply_multi_target,
    delete_plan,
    json_plan,
    timer_and_item_transaction,
)
from .transaction_journal import journal_directory
from .timezone_policy import now as timezone_now
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
    raise ValueError(
        "timer requires start, pause, resume, stop, status, summary, or cancel."
    )


def start_timer(args):
    result = start_timer_transaction(
        args.path,
        args.item_id,
        note=getattr(args, "note", None),
        config=getattr(args, "config_data", None),
        expected_item_revision=getattr(args, "item_revision", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revisions=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Started timer for %s (%s) at %s\n"
        % (result["id"], result["title"], result["started_at"])
    )
    return 0


def stop_timer(args):
    result = stop_timer_transaction(
        path=getattr(args, "path", None),
        item_id=getattr(args, "item_id", None),
        config=getattr(args, "config_data", None),
        expected_item_revision=getattr(args, "item_revision", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revisions=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Stopped timer for %s (%s): +%s total %s\n"
        % (
            result["id"],
            result["title"],
            result["elapsed_added"],
            result["elapsed_total"],
        )
    )
    sys.stdout.write(result["updated_line"] + "\n")
    return 0


def pause_timer(args):
    result = pause_timer_transaction(
        config=getattr(args, "config_data", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revision=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Paused timer for %s: elapsed %s\n" % (result["id"], result["elapsed"])
    )
    return 0


def resume_timer(args):
    result = resume_timer_transaction(
        config=getattr(args, "config_data", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revision=bool(getattr(args, "require_revisions", False)),
    )
    sys.stdout.write(
        "Resumed timer for %s at %s\n" % (result["id"], result["started_at"])
    )
    return 0


def cancel_timer(args):
    result = cancel_timer_transaction(
        config=getattr(args, "config_data", None),
        expected_timer_revision=getattr(args, "timer_revision", None),
        require_revision=bool(getattr(args, "require_revisions", False)),
    )
    if result["canceled"]:
        sys.stdout.write("Canceled running timer.\n")
    else:
        sys.stdout.write("No running timer.\n")
    return 0


def start_timer_transaction(
    path,
    item_id,
    note=None,
    config=None,
    expected_item_revision=None,
    expected_timer_revision=None,
    require_revisions=False,
):
    config = config or {}
    state_file = timer_state_file(config)
    timer_snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    item_snapshot = mutation.read_text_snapshot(path)
    timer_expected = _resolve_revision(
        expected_timer_revision,
        timer_snapshot.content_hash,
        require_revisions,
        "timer_revision",
    )
    item_expected = _resolve_revision(
        expected_item_revision,
        item_snapshot.content_hash,
        require_revisions,
        "item_revision",
    )
    if timer_snapshot.exists:
        raise ValueError(
            "A timer is already running. Use `lifetxt timer status` or `lifetxt timer stop` first."
        )
    item = find_item_in_text(
        item_snapshot.text, item_id, id_key_from_config(config), path
    )
    current_now = _now()
    state = OrderedDict(
        [
            ("id", item_id),
            ("file", os.path.abspath(path)),
            ("started_at", format_datetime(current_now)),
            ("accumulated_minutes", 0),
            ("paused_at", ""),
            ("note", note or ""),
        ]
    )

    def item_transform(text):
        found = find_item_in_text(text, item_id, id_key_from_config(config), path)
        if found.status == "[ ]":
            return updated_item_text(
                text, item_id, id_key_from_config(config), status="[/]"
            )[0]
        return text

    result = timer_and_item_transaction(
        state_file,
        lambda _current: state,
        timer_expected,
        path,
        item_transform,
        item_expected,
        operation="timer.start",
        journal_dir=journal_directory(config, writable_path=path),
    )
    return _timer_result(
        result,
        {
            "running": True,
            "id": item_id,
            "title": item.title,
            "started_at": state["started_at"],
            "elapsed_minutes": 0,
            "elapsed": "0m",
        },
    )


def stop_timer_transaction(
    path=None,
    item_id=None,
    config=None,
    expected_item_revision=None,
    expected_timer_revision=None,
    require_revisions=False,
):
    config = config or {}
    state_file = timer_state_file(config)
    timer_snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    if not timer_snapshot.exists:
        raise ValueError("No running timer.")
    state = _state_from_snapshot(timer_snapshot)
    resolved_id = item_id or state.get("id")
    if item_id and item_id != state.get("id"):
        raise ValueError(
            "Running timer is for %s, not %s." % (state.get("id"), item_id)
        )
    resolved_path = path or state.get("file")
    if not resolved_path:
        raise ValueError("Timer state does not identify its life.txt file.")
    item_snapshot = mutation.read_text_snapshot(resolved_path)
    timer_expected = _resolve_revision(
        expected_timer_revision,
        timer_snapshot.content_hash,
        require_revisions,
        "timer_revision",
    )
    item_expected = _resolve_revision(
        expected_item_revision,
        item_snapshot.content_hash,
        require_revisions,
        "item_revision",
    )
    minutes = state_elapsed_minutes(state, _now())
    key = id_key_from_config(config)
    item = find_item_in_text(item_snapshot.text, resolved_id, key, resolved_path)
    existing = sum(parse_elapsed(value) for value in item.details.get("elapsed", []))
    total = existing + minutes
    updated_line_holder = []

    def item_transform(text):
        replacement, line = updated_item_text(
            text,
            resolved_id,
            key,
            set_details={"elapsed": [format_elapsed(total)]},
        )
        updated_line_holder[:] = [line]
        return replacement

    result = timer_and_item_transaction(
        state_file,
        lambda current: current,
        timer_expected,
        resolved_path,
        item_transform,
        item_expected,
        operation="timer.stop",
        timer_delete=True,
        journal_dir=journal_directory(config, writable_path=resolved_path),
    )
    return _timer_result(
        result,
        {
            "running": False,
            "id": resolved_id,
            "title": item.title,
            "elapsed_minutes_added": minutes,
            "elapsed_added": format_elapsed(minutes),
            "elapsed_total_minutes": total,
            "elapsed_total": format_elapsed(total),
            "updated_line": updated_line_holder[0],
        },
    )


def pause_timer_transaction(
    config=None, expected_timer_revision=None, require_revision=False
):
    config = config or {}
    state_file = timer_state_file(config)
    snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    if not snapshot.exists:
        raise ValueError("No running timer.")
    state = _state_from_snapshot(snapshot)
    if state.get("paused_at"):
        raise ValueError("Timer is already paused.")
    expected = _resolve_revision(
        expected_timer_revision,
        snapshot.content_hash,
        require_revision,
        "timer_revision",
    )
    current_now = _now()
    minutes = state_elapsed_minutes(state, current_now)

    def transform(current):
        current = OrderedDict(current)
        current["accumulated_minutes"] = minutes
        current["paused_at"] = format_datetime(current_now)
        return current

    result = apply_multi_target(
        [json_plan(state_file, transform, expected)],
        operation="timer.pause",
        journal_dir=journal_directory(config, writable_path=state_file),
    )
    return _timer_result(
        result,
        {
            "running": True,
            "paused": True,
            "id": state.get("id"),
            "elapsed_minutes": minutes,
            "elapsed": format_elapsed(minutes),
            "paused_at": format_datetime(current_now),
        },
    )


def resume_timer_transaction(
    config=None, expected_timer_revision=None, require_revision=False
):
    config = config or {}
    state_file = timer_state_file(config)
    snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    if not snapshot.exists:
        raise ValueError("No running timer.")
    state = _state_from_snapshot(snapshot)
    if not state.get("paused_at"):
        raise ValueError("Timer is not paused.")
    expected = _resolve_revision(
        expected_timer_revision,
        snapshot.content_hash,
        require_revision,
        "timer_revision",
    )
    current_now = _now()

    def transform(current):
        current = OrderedDict(current)
        current["started_at"] = format_datetime(current_now)
        current["paused_at"] = ""
        return current

    result = apply_multi_target(
        [json_plan(state_file, transform, expected)],
        operation="timer.resume",
        journal_dir=journal_directory(config, writable_path=state_file),
    )
    return _timer_result(
        result,
        {
            "running": True,
            "paused": False,
            "id": state.get("id"),
            "started_at": format_datetime(current_now),
        },
    )


def cancel_timer_transaction(
    config=None, expected_timer_revision=None, require_revision=False
):
    config = config or {}
    state_file = timer_state_file(config)
    snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    if not snapshot.exists:
        return {
            "running": False,
            "canceled": False,
            "timer_revision": MISSING_HASH,
            "transaction_id": None,
            "journal_path": None,
        }
    state = _state_from_snapshot(snapshot)
    expected = _resolve_revision(
        expected_timer_revision,
        snapshot.content_hash,
        require_revision,
        "timer_revision",
    )
    result = apply_multi_target(
        [delete_plan(state_file, expected, kind="json")],
        operation="timer.cancel",
        journal_dir=journal_directory(config, writable_path=state_file),
    )
    return _timer_result(
        result,
        {"running": False, "canceled": True, "id": state.get("id")},
    )


def timer_status_data(config=None, paths=None):
    config = config or {}
    state_file = timer_state_file(config)
    snapshot = mutation.read_text_snapshot(state_file, allow_missing=True)
    if not snapshot.exists:
        return {"running": False, "timer_revision": MISSING_HASH}
    state = _state_from_snapshot(snapshot)
    minutes = state_elapsed_minutes(state, _now())
    path = state.get("file")
    item_revision = None
    title = "unknown"
    if path:
        try:
            item_snapshot = mutation.read_text_snapshot(path)
            item_revision = item_snapshot.content_hash
            item = find_item_in_text(
                item_snapshot.text, state.get("id"), id_key_from_config(config), path
            )
            title = item.title
        except (OSError, ValueError):
            pass
    return {
        "running": True,
        "id": state.get("id"),
        "title": title,
        "file": path,
        "started_at": state.get("started_at"),
        "paused": bool(state.get("paused_at")),
        "paused_at": state.get("paused_at") or "",
        "elapsed_minutes": minutes,
        "elapsed": format_elapsed(minutes),
        "timer_revision": snapshot.content_hash,
        "item_revision": item_revision,
    }


def _resolve_revision(provided, actual, required, name):
    if provided is None or str(provided).strip() == "":
        if required:
            raise ValueError("%s is required." % name)
        return actual
    return str(provided).strip()


def _state_from_snapshot(snapshot):
    try:
        return json.loads(snapshot.text, object_pairs_hook=OrderedDict)
    except ValueError as exc:
        raise ValueError("Timer state is invalid JSON: %s" % exc)


def _timer_result(result, values):
    payload = OrderedDict(values)
    payload["operation"] = result.operation
    payload["transaction_id"] = result.transaction_id
    payload["journal_path"] = result.journal_path
    payload["recovery_required"] = result.recovery_required
    for target in result.targets:
        if target.kind == "json":
            payload["timer_revision"] = target.after_hash
        elif target.kind == "text":
            payload["item_revision"] = target.after_hash
    return payload


def status_timer(args):
    data = timer_status_data(
        config=getattr(args, "config_data", None),
        paths=getattr(args, "paths", None),
    )
    if not data.get("running"):
        sys.stdout.write("No running timer.\n")
        return 0
    if data.get("paused"):
        sys.stdout.write(
            "Paused: %s (%s)  elapsed: %s  paused: %s\n"
            % (data["id"], data["title"], data["elapsed"], data.get("paused_at", ""))
        )
    else:
        sys.stdout.write(
            "Running: %s (%s)  elapsed: %s  started: %s\n"
            % (data["id"], data["title"], data["elapsed"], data.get("started_at", ""))
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
        project = (
            item.details.get("project", [""])[0] if item.details.get("project") else ""
        )
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
                (
                    "by_project",
                    OrderedDict(
                        (key, {"minutes": value, "elapsed": format_elapsed(value)})
                        for key, value in by_project.items()
                    ),
                ),
            ]
        )
        sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(format_summary(rows, total, by_project, args.start, args.end))
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
        lines.append(
            "%s  %s"
            % ("Total".ljust(width_id + width_title + 2), format_elapsed(total))
        )
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
    return find_item_in_text(_read_text(path), item_id, key, path)


def find_item_in_text(text, item_id, key, source="<text>"):
    items, diagnostics = parse_text(text, id_key=key)
    _raise_on_errors(diagnostics)
    matches = [item for item in items if item_id in item.details.get(key, [])]
    if not matches:
        raise ValueError("No item found with %s:%s in %s." % (key, item_id, source))
    if len(matches) > 1:
        raise ValueError(
            "Multiple items found with %s:%s in %s." % (key, item_id, source)
        )
    return matches[0]


def updated_item_text(text, item_id, key, status=None, set_details=None):
    lines = text.splitlines(True)
    item = find_item_in_text(text, item_id, key)
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
    return "".join(lines), updated


def update_item_in_file(
    path, item_id, key, status=None, set_details=None, expected_revision=None
):
    from .write_operations import mutate_items

    result = mutate_items(
        path,
        [{"id": item_id, "status": status, "set_details": set_details or {}}],
        id_key=key,
        expected_revision=expected_revision,
        operation="timer.item_update",
    )
    snapshot = mutation.read_text_snapshot(path)
    item = find_item_in_text(snapshot.text, item_id, key, path)
    return item_to_line(item)


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
    value = timezone_now().replace(microsecond=0)
    # Existing timer state is intentionally stored as a local wall time without
    # an offset.  The shared timezone context selects that wall clock while
    # preserving backward-compatible serialized values.
    return value.replace(tzinfo=None)


def _read_state(path):
    if not os.path.exists(path):
        raise ValueError("No running timer.")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def _write_json(path, data):
    atomic_write_json(path, data)


def _read_text(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _write_text(path, text):
    atomic_write_text(path, text)


def _line_ending(line):
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\r"):
        return "\r"
    return "\n"


def _raise_on_errors(diagnostics):
    errors = [
        diagnostic for diagnostic in diagnostics if diagnostic.severity == "error"
    ]
    if errors:
        raise ValueError(errors[0].format())


def _id_key(args):
    return id_key_from_config(getattr(args, "config_data", None) or {})


def _first(values):
    if values:
        return values[0]
    return None
