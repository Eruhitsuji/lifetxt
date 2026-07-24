"""Journal-backed compound work-session operations.

A work session touches the timer state and life.txt semantics together.  Start
updates the task and opens presence in the same staged life.txt replacement;
stop records elapsed time, optionally completes the task, closes presence, and
removes timer state as one recoverable transaction.
"""
from __future__ import unicode_literals

import os
from collections import OrderedDict

from . import mutation
from .config import config_section
from .ids import id_key_from_config
from .multi_target import apply_multi_target, delete_plan, json_plan, text_plan
from .presence import status_transition
from .timer import (
    _resolve_revision,
    _state_from_snapshot,
    _timer_result,
    _now,
    find_item_in_text,
    format_datetime,
    format_elapsed,
    state_elapsed_minutes,
    timer_state_file,
)
from .timeutil import parse_elapsed
from .timezone_policy import now as timezone_now
from .transaction_journal import journal_directory
from .write_operations import transform_items_text


def start_work_transaction(
    path,
    item_id,
    state="busy",
    use_timer=True,
    use_presence=True,
    config=None,
    expected_item_revision=None,
    expected_timer_revision=None,
    require_revisions=False,
):
    config = config or {}
    item_snapshot = mutation.read_text_snapshot(path)
    item_expected = _resolve_revision(
        expected_item_revision, item_snapshot.content_hash, require_revisions,
        "item_revision",
    )
    key = id_key_from_config(config)
    item = find_item_in_text(item_snapshot.text, item_id, key, path)
    plans = []
    timer_path = timer_state_file(config)
    timer_snapshot = mutation.read_text_snapshot(timer_path, allow_missing=True)
    timer_expected = _resolve_revision(
        expected_timer_revision, timer_snapshot.content_hash, require_revisions and use_timer,
        "timer_revision",
    )
    moment = _now()
    timer_state = None
    if use_timer:
        if timer_snapshot.exists:
            running = _state_from_snapshot(timer_snapshot)
            raise ValueError("A timer is already running for %s." % running.get("id"))
        timer_state = OrderedDict([
            ("id", item_id),
            ("file", os.path.abspath(path)),
            ("started_at", format_datetime(moment)),
            ("accumulated_minutes", 0),
            ("paused_at", ""),
            ("note", ""),
        ])
        plans.append(json_plan(
            timer_path, lambda _current: timer_state, timer_expected,
            create=True, default={},
        ))

    opened = {"line": "", "closed": []}

    def life_transform(text):
        replacement = text
        current = find_item_in_text(replacement, item_id, key, path)
        if current.status == "[ ]":
            replacement = transform_items_text(
                replacement, [{"id": item_id, "status": "[/]"}], id_key=key
            )
        if use_presence:
            transition = status_transition(
                replacement,
                state=state,
                title=item.title,
                person="self",
                moment=moment,
                details={"project": item.details.get("project", [])},
                id_key=key,
                close_only=False,
            )
            opened["line"] = transition.opened
            opened["closed"] = list(transition.closed or [])
            replacement = transition.text
        return replacement

    plans.append(text_plan(
        path, life_transform, item_expected,
        validate=lambda value: _validate_life(value, key),
    ))
    result = apply_multi_target(
        plans,
        operation="work.start",
        journal_dir=journal_directory(config, writable_path=path),
        config=config,
    )
    payload = _timer_result(result, {
        "running": bool(use_timer),
        "id": item_id,
        "title": item.title,
        "started_at": format_datetime(moment) if use_timer else "",
        "presence": state if use_presence else "",
        "presence_opened": opened["line"],
        "presence_closed": opened["closed"],
    })
    if not use_timer:
        payload["timer_revision"] = timer_snapshot.content_hash
    return payload


def stop_work_transaction(
    path=None,
    done=False,
    close_presence=True,
    config=None,
    expected_item_revision=None,
    expected_timer_revision=None,
    require_revisions=False,
):
    config = config or {}
    timer_path = timer_state_file(config)
    timer_snapshot = mutation.read_text_snapshot(timer_path, allow_missing=True)
    if not timer_snapshot.exists:
        raise ValueError("No running timer.")
    state = _state_from_snapshot(timer_snapshot)
    resolved_path = path or state.get("file")
    if not resolved_path:
        raise ValueError("Timer state does not identify its life.txt file.")
    item_id = state.get("id")
    item_snapshot = mutation.read_text_snapshot(resolved_path)
    timer_expected = _resolve_revision(
        expected_timer_revision, timer_snapshot.content_hash, require_revisions,
        "timer_revision",
    )
    item_expected = _resolve_revision(
        expected_item_revision, item_snapshot.content_hash, require_revisions,
        "item_revision",
    )
    key = id_key_from_config(config)
    item = find_item_in_text(item_snapshot.text, item_id, key, resolved_path)
    moment = _now()
    minutes = state_elapsed_minutes(state, moment)
    existing = sum(parse_elapsed(value) for value in item.details.get("elapsed", []))
    total = existing + minutes
    closed = {"rows": []}
    done_value = timezone_now().replace(tzinfo=None)
    done_precision = str(config_section(config, "done").get("precision") or "date").lower()
    stamp = done_value.strftime("%Y-%m-%dT%H:%M") if done_precision == "datetime" else done_value.date().isoformat()

    def life_transform(text):
        details = {"elapsed": [format_elapsed(total)]}
        status = None
        if done:
            details["done"] = [stamp]
            status = "[x]"
        replacement = transform_items_text(
            text, [{"id": item_id, "status": status, "set_details": details}], id_key=key
        )
        if close_presence:
            transition = status_transition(
                replacement,
                person="self",
                moment=moment,
                id_key=key,
                close_only=True,
            )
            closed["rows"] = list(transition.closed or [])
            replacement = transition.text
        return replacement

    result = apply_multi_target(
        [
            delete_plan(timer_path, timer_expected, kind="json"),
            text_plan(
                resolved_path, life_transform, item_expected,
                validate=lambda value: _validate_life(value, key),
            ),
        ],
        operation="work.stop",
        journal_dir=journal_directory(config, writable_path=resolved_path),
        config=config,
    )
    return _timer_result(result, {
        "running": False,
        "id": item_id,
        "title": item.title,
        "elapsed_minutes_added": minutes,
        "elapsed_added": format_elapsed(minutes),
        "elapsed_total_minutes": total,
        "elapsed_total": format_elapsed(total),
        "done": bool(done),
        "done_value": stamp if done else "",
        "presence_closed": closed["rows"],
    })


def _validate_life(text, id_key):
    from .parser import parse_text
    _items, diagnostics = parse_text(text, id_key=id_key)
    errors = [row for row in diagnostics if row.severity == "error"]
    if errors:
        raise ValueError(errors[0].format())
    return True
