"""Protocol-neutral read helpers shared by Web and MCP surfaces."""

import os

from .diagnostic_contract import diagnostics_to_output
from .ids import duplicate_id_diagnostics, id_key_from_config
from .links import reference_diagnostics
from .parser import parse_text
from .timeutil import format_datetime, parse_date_or_datetime


def assert_unique_ids(items, key="id"):
    """Reject authoritative writes when a workspace contains duplicate IDs."""
    duplicates = duplicate_id_diagnostics(items, key=key)
    if any(row.code == "W213" for row in duplicates):
        raise ValueError("Authoritative write rejected: workspace IDs must be unique.")


def assert_unique_workspace_ids(
    paths, config, normalize_server_paths, read_text, is_generated_path
):
    """Validate existing source IDs before a Web or MCP write is exposed."""
    existing = [
        path
        for path in normalize_server_paths(paths)
        if path != "-" and os.path.isfile(path)
    ]
    if not existing:
        return
    items, _diagnostics = read_life_inputs(
        existing, config, normalize_server_paths, read_text, is_generated_path
    )
    assert_unique_ids(items, key=id_key_from_config(config or {}))


def read_life_inputs(
    paths, config, normalize_server_paths, read_text, is_generated_path
):
    normalized = normalize_server_paths(paths)
    include_source = len(normalized) > 1
    id_key = id_key_from_config(config or {})
    items = []
    diagnostics = []
    for path in normalized:
        path_items, path_diagnostics = parse_text(
            read_text(path), id_key=id_key, check_ids=False, check_references=False
        )
        generated = is_generated_path(path, config)
        for item in path_items:
            item.generated = generated
        if include_source:
            for item in path_items:
                item.source = path
            for diagnostic in path_diagnostics:
                diagnostic.source = path
        items.extend(path_items)
        diagnostics.extend(path_diagnostics)
    diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
    diagnostics.extend(reference_diagnostics(items, key=id_key))
    return items, diagnostics


def sort_items(items, sort_key="line", order="asc"):
    reverse = str(order).lower() in ("desc", "descending", "-1")
    key_name = str(sort_key or "line").lower().replace("-", "_")
    supported = {
        "line",
        "status",
        "type",
        "kind",
        "title",
        "source",
        "time",
        "due",
        "from",
        "to",
        "notify_at",
        "notify_from",
        "notify_to",
        "on",
        "updated",
        "created",
        "progress",
    }
    if key_name not in supported:
        key_name = "line"
    keyed = [(sort_key_for_item(item, key_name), item) for item in items]
    present = [entry for entry in keyed if entry[0][0] == 0]
    missing = [entry for entry in keyed if entry[0][0] != 0]
    present.sort(key=lambda entry: entry[0], reverse=reverse)
    missing.sort(key=lambda entry: entry[0])
    return [entry[1] for entry in present + missing]


def sort_key_for_item(item, key_name):
    if key_name == "line":
        return (0, item.line if item.line is not None else 999999999)
    if key_name == "status":
        return (0, item.status or "", item.line or 0)
    if key_name in ("type", "kind"):
        return (0, item.kind or "", item.line or 0)
    if key_name == "title":
        return (0, item.title.lower(), item.line or 0)
    if key_name == "source":
        return (0, getattr(item, "source", "") or "", item.line or 0)
    if key_name == "progress":
        # A missing or unparseable progress: sorts to the end (tuple[0]=1),
        # matching the pattern date-based keys already use here -- never
        # implicitly treated as 0% (#652).
        from .progress import ProgressValueError, parse_progress

        values = item.details.get("progress")
        if values:
            try:
                return (0, parse_progress(values[0]).ratio, item.line or 0)
            except ProgressValueError:
                pass
        return (1, "", item.line or 0)
    keys = (
        (
            "from",
            "notify_at",
            "notify_from",
            "due",
            "do",
            "on",
            "at",
            "to",
            "notify_to",
            "updated",
            "created",
        )
        if key_name == "time"
        else (key_name,)
    )
    for key in keys:
        values = item.details.get(key)
        if values:
            parsed = parse_date_or_datetime(values[0])
            return (
                0,
                format_datetime(parsed) if parsed is not None else values[0],
                item.line or 0,
            )
    return (1, "", item.line or 0)


def limit_items(items, limit):
    if limit in (None, ""):
        return items
    try:
        amount = int(limit)
    except (TypeError, ValueError):
        return items
    return items if amount < 0 else items[:amount]


def find_item_by_id(items, item_id, kind=None, key="id"):
    matches = [
        item
        for item in items
        if (kind is None or item.kind == kind) and item_id in item.details.get(key, [])
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("Multiple items found with id:%s." % item_id)
    return matches[0]
