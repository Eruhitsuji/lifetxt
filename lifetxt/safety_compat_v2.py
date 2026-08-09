"""Compatibility fixes for the P0 safety layer discovered by the full matrix."""

from __future__ import unicode_literals

import contextvars
import os
import re


_INSTALLED = False
_QUICK_KNOWN_IDS = contextvars.ContextVar("lifetxt_quick_known_ids", default=None)

_RECORD_OWNED_KEYS = {
    "project": frozenset(
        (
            "record",
            "id",
            "project",
            "state",
            "owner",
            "assignee",
            "area",
            "visibility",
            "due",
            "do",
            "from",
        )
    ),
    "milestone": frozenset(("record", "id", "project", "due", "owner", "assignee")),
    "risk": frozenset(
        ("record", "id", "project", "severity", "state", "owner", "assignee")
    ),
    "issue": frozenset(
        ("record", "id", "project", "severity", "state", "owner", "assignee")
    ),
    "decision": frozenset(
        ("record", "id", "project", "on", "at", "owner", "assignee")
    ),
    "meeting": frozenset(
        (
            "record",
            "id",
            "project",
            "on",
            "at",
            "owner",
            "assignee",
            "attendee",
            "loc",
        )
    ),
    "ticket": frozenset(
        (
            "record",
            "id",
            "tracker",
            "ticket_status",
            "priority",
            "severity",
            "reporter",
            "assignee",
            "watcher",
            "component",
            "category",
            "version",
            "milestone",
            "sprint",
            "est",
            "elapsed",
            "story_points",
            "resolution",
            "closed_by",
            "branch",
            "commit",
            "pr",
            "build",
            "project",
            "parent",
            "depends_on",
            "blocks",
            "related",
            "duplicate_of",
            "replaced_by",
        )
    ),
}
_RECORD_LIFECYCLE_STATE_MARKERS = frozenset(("project", "risk", "issue"))
_W106_KEY_RE = re.compile(r"^Detail key '([^']+)' is custom for type ")


def install_safety_compat_v2():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_record_owned_validation()
    _patch_cli_timezone_installer()
    _patch_doctor_dispatch()
    _patch_revision_conflict_output()
    _patch_stable_diagnostic_shape()
    _INSTALLED = True


def _record_marker(item):
    values = getattr(item, "details", {}).get("record") or []
    return str(values[0]).lower() if values else None


def _w106_key(diagnostic):
    match = _W106_KEY_RE.match(str(getattr(diagnostic, "message", "")))
    return match.group(1) if match else None


def _patch_record_owned_validation():
    """Keep generic validation aligned with documented record-specific fields.

    Project and Ticket features deliberately model richer records as ordinary
    Note/Task items plus ``record:*`` metadata.  The generic validator remains
    permissive and should still warn about arbitrary custom keys, but fields that
    lifetxt itself owns for a known record marker are not custom.  Likewise,
    ``state:`` on Project/Risk/Issue records is a record lifecycle value, not a
    presence-state value.
    """
    from . import parser, validator

    original = validator.validate_item
    if getattr(original, "_lifetxt_record_owned_validation_v2", False):
        return

    def validate_item(item):
        diagnostics = original(item)
        marker = _record_marker(item)
        owned = _RECORD_OWNED_KEYS.get(marker)
        if not owned:
            return diagnostics

        filtered = []
        for diagnostic in diagnostics:
            code = str(getattr(diagnostic, "code", "")).upper()
            if code == "W106" and _w106_key(diagnostic) in owned:
                continue
            if code == "W207" and marker in _RECORD_LIFECYCLE_STATE_MARKERS:
                continue
            filtered.append(diagnostic)
        return filtered

    validate_item._lifetxt_record_owned_validation_v2 = True
    validator.validate_item = validate_item
    # parser.py imports validate_item by value, so update its binding too.
    parser.validate_item = validate_item


def _patch_cli_timezone_installer():
    from . import runtime_safety_v2

    def install_cli_timezone_context(cli_module):
        from .config import load_config
        from .safety_foundation import read_text_exact
        from .timezone_policy import (
            cli_timezone_candidate_paths,
            resolve_timezone_name,
            timezone_context,
        )

        _patch_capture_commands(cli_module)
        current = cli_module.main
        if getattr(current, "_lifetxt_timezone_context_v2", False):
            return

        def main(argv=None):
            raw = list(argv or [])
            config_path = None
            workspace_name = None
            for index, value in enumerate(raw):
                if value == "--config" and index + 1 < len(raw):
                    config_path = raw[index + 1]
                elif value.startswith("--config="):
                    config_path = value.split("=", 1)[1]
                elif value == "--workspace" and index + 1 < len(raw):
                    workspace_name = raw[index + 1]
                elif value.startswith("--workspace="):
                    workspace_name = value.split("=", 1)[1]
            config = load_config(config_path) or {}
            candidates = cli_timezone_candidate_paths(raw, config, workspace_name)
            text = ""
            for path in candidates:
                if path and path != "-" and os.path.exists(path):
                    try:
                        text, _raw, _bom = read_text_exact(path)
                        break
                    except OSError:
                        continue
            name = resolve_timezone_name(config, text=text)
            with timezone_context(name):
                return current(argv)

        main._lifetxt_timezone_context_v2 = True
        cli_module.main = main

    runtime_safety_v2.install_cli_timezone_context = install_cli_timezone_context


def _configured_item_ids(cli_module, args, extra_paths=None):
    from .ids import collect_item_ids, id_key_from_config
    from .parser import parse_text

    config = cli_module._config(args)
    key = id_key_from_config(config)
    paths = []
    for path in cli_module.config_paths(config) or []:
        if path not in paths:
            paths.append(path)
    for path in extra_paths or []:
        if path and path not in paths:
            paths.append(path)

    values = set()
    for path in paths:
        if not path or path == "-" or not os.path.exists(path):
            continue
        try:
            text = cli_module.read_text(path)
        except OSError:
            continue
        items, _diagnostics = parse_text(
            text,
            id_key=key,
            check_ids=False,
            check_references=False,
        )
        values.update(collect_item_ids(items, key=key))
    return values


def _w215_target(diagnostic):
    if str(getattr(diagnostic, "code", "")).upper() != "W215":
        return None
    message = str(getattr(diagnostic, "message", ""))
    prefix = "Reference "
    suffix = " does not match any "
    if not message.startswith(prefix) or suffix not in message:
        return None
    reference = message[len(prefix) :].split(suffix, 1)[0]
    if ":" not in reference:
        return None
    return reference.split(":", 1)[1]


def _patch_capture_commands(cli_module):
    """Align Project/quick capture with auto-ID and workspace reference context."""
    if getattr(cli_module, "_lifetxt_capture_validation_v2", False):
        return

    from .ids import (
        auto_ids_enabled,
        ensure_item_id,
        id_key_from_config,
        id_prefix_for_item,
    )
    from .parser import parse_text as parser_parse_text
    from .serializer import item_to_line

    original_emit_project_line = cli_module._emit_project_line

    def emit_project_line(args, line):
        config = cli_module._config(args)
        if auto_ids_enabled(config):
            key = id_key_from_config(config)
            items, _diagnostics = parser_parse_text(
                line + "\n",
                id_key=key,
                check_ids=False,
                check_references=False,
            )
            if items:
                target = cli_module._project_write_target(args)
                existing_ids = _configured_item_ids(cli_module, args, [target])
                item = items[0]
                ensure_item_id(
                    item,
                    existing_ids=existing_ids,
                    key=key,
                    prefix=id_prefix_for_item(item, config),
                )
                line = item_to_line(item)
        return original_emit_project_line(args, line)

    emit_project_line._lifetxt_project_auto_id_v2 = True
    cli_module._emit_project_line = emit_project_line

    original_cli_parse_text = cli_module.parse_text

    def parse_text_with_capture_context(text, *args, **kwargs):
        items, diagnostics = original_cli_parse_text(text, *args, **kwargs)
        known_ids = _QUICK_KNOWN_IDS.get()
        if known_ids is None:
            return items, diagnostics
        diagnostics = [
            diagnostic
            for diagnostic in diagnostics
            if not (
                _w215_target(diagnostic) is not None
                and _w215_target(diagnostic) in known_ids
            )
        ]
        return items, diagnostics

    parse_text_with_capture_context._lifetxt_quick_reference_context_v2 = True
    cli_module.parse_text = parse_text_with_capture_context

    original_quick = cli_module.command_quick

    def command_quick(args):
        config = cli_module._config(args)
        destination = getattr(args, "append", None) or cli_module.config_write_file(config)
        known_ids = _configured_item_ids(cli_module, args, [destination])
        token = _QUICK_KNOWN_IDS.set(known_ids)
        try:
            return original_quick(args)
        finally:
            _QUICK_KNOWN_IDS.reset(token)

    command_quick._lifetxt_reference_context_v2 = True
    cli_module.command_quick = command_quick

    # argparse stores function objects while build_parser() runs after this patch,
    # so future parsers pick up the wrapped command automatically.
    cli_module._lifetxt_capture_validation_v2 = True


def _patch_doctor_dispatch():
    from . import extra_cli

    original = extra_cli.main
    if getattr(original, "_lifetxt_doctor_dispatch_v2", False):
        return

    def main(argv=None, config_path=None, workspace_name=None):
        raw = list(argv or [])
        if raw and raw[0] == "doctor" and "--workspace-safety" not in raw:
            raw.insert(1, "--workspace-safety")
        return original(
            raw,
            config_path=config_path,
            workspace_name=workspace_name,
        )

    main._lifetxt_doctor_dispatch_v2 = True
    extra_cli.main = main


def _patch_revision_conflict_output():
    from . import extra_cli, extra_safety
    from .mutation import MutationConflict

    original = extra_safety.command_safety
    if getattr(original, "_lifetxt_revision_conflict_output_v2", False):
        return

    def command_safety(args, config_data):
        try:
            return original(args, config_data)
        except MutationConflict as exc:
            if getattr(args, "safety_action", None) != "revisions":
                raise
            report = {
                "ok": False,
                "error": "CONFLICT",
                "operation": exc.operation,
                "path": exc.path,
                "expected_revision": exc.expected_hash,
                "current_revision": exc.actual_hash,
                "message": str(exc),
            }
            return extra_safety._output(report, args, failure=True)

    command_safety._lifetxt_revision_conflict_output_v2 = True
    extra_safety.command_safety = command_safety
    extra_cli.command_safety = command_safety


def _patch_stable_diagnostic_shape():
    from . import release_policy, safety_foundation, workspace_diagnostics

    original = workspace_diagnostics.stable_file_diagnostics
    if getattr(original, "_lifetxt_complete_shape_v2", False):
        return

    def stable_file_diagnostics(path):
        report = original(path)
        rows = []
        for raw in report.get("diagnostics") or []:
            row = dict(raw)
            row.setdefault("severity", "error")
            row.setdefault("code", "P000")
            row.setdefault("message", "")
            row.setdefault("source", path)
            row.setdefault("line", None)
            row.setdefault("column", None)
            row.setdefault(
                "span",
                {
                    "start": {"line": row.get("line"), "column": row.get("column")},
                    "end": {"line": row.get("line"), "column": row.get("column")},
                },
            )
            row.setdefault("hint", "")
            rows.append(row)
        rows = workspace_diagnostics._sort_diagnostics(rows)
        return {
            "ok": not any(row.get("severity") == "error" for row in rows),
            "item_count": report.get("item_count", 0),
            "diagnostics": rows,
        }

    stable_file_diagnostics._lifetxt_complete_shape_v2 = True
    workspace_diagnostics.stable_file_diagnostics = stable_file_diagnostics
    safety_foundation.stable_diagnostics = stable_file_diagnostics
    release_policy.stable_diagnostics = stable_file_diagnostics
