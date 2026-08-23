"""Read-only data integrity reporting for lifetxt."""

from __future__ import annotations

import json
import os
from collections import OrderedDict

from .attachments import ATTACHMENT_KEYS, attachment_diagnostics
from .config import config_paths
from .diagnostic_contract import diagnostic_category
from .ids import duplicate_id_diagnostics, id_key_from_config
from .links import reference_diagnostics
from .model import Diagnostic
from .parser import parse_text
from .paths import expand_paths


SCHEMA = "integrity-v1"


def build_integrity_report(paths=None, config=None, verify_files=False):
    """Build a read-only integrity report.

    This function intentionally performs no write, repair, migration, archive,
    cleanup, or recovery action. It only reads the selected sources and
    normalizes diagnostics produced by existing lifetxt validators.
    """

    config = config or {}
    normalized = _normalize_paths(paths, config)
    id_key = id_key_from_config(config)
    diagnostics = []
    items = []
    line_ids = {}
    existing_paths = []

    for path in normalized:
        if path != "-" and not os.path.exists(path):
            diagnostics.append(
                _row(
                    severity="error",
                    code="I001",
                    category="source",
                    message="Input source does not exist: %s." % path,
                    hint="Create the file, remove it from the workspace, or pass a different path.",
                    source_file=path,
                    check_state="blocked",
                )
            )
            continue
        if path == "-":
            diagnostics.append(
                _row(
                    severity="info",
                    code="I002",
                    category="source",
                    message="Standard input cannot be re-read by workspace or ticket checks.",
                    hint="Pass a file path when full integrity context is needed.",
                    source_file="stdin",
                    check_state="skipped",
                )
            )
            continue
        existing_paths.append(path)
        with open(path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
        path_items, path_diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        for item in path_items:
            item.source = path
            values = item.details.get(id_key) or []
            if values:
                line_ids[(path, item.line)] = str(values[0])
        for diagnostic in path_diagnostics:
            diagnostic.source = path
        items.extend(path_items)
        diagnostics.extend(_diagnostic_rows(path_diagnostics, line_ids))
        if not path_diagnostics:
            diagnostics.append(
                _row(
                    severity="info",
                    code="I100",
                    category="syntax",
                    message="Parsed %s without diagnostics." % path,
                    hint="",
                    source_file=path,
                    check_state="passed",
                )
            )

    cross_diagnostics = []
    if items:
        cross_diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
        cross_diagnostics.extend(reference_diagnostics(items, key=id_key))
        cross_diagnostics.extend(_attachment_rows(items, config, verify_files))
        cross_diagnostics.extend(_ticket_rows(items, config, id_key))
    else:
        diagnostics.append(
            _row(
                severity="info",
                code="I003",
                category="syntax",
                message="No parseable life.txt items were loaded.",
                hint="Pass one or more life.txt files to run item-level checks.",
                check_state="skipped",
            )
        )
    diagnostics.extend(_diagnostic_rows(cross_diagnostics, line_ids))
    diagnostics.extend(_workspace_rows(config))

    summary = _summary(diagnostics)
    return OrderedDict(
        (
            ("schema", SCHEMA),
            (
                "ok",
                not any(
                    row["effective_severity"] in ("error", "warning")
                    for row in diagnostics
                ),
            ),
            ("paths", normalized),
            ("checked_paths", existing_paths),
            ("item_count", len(items)),
            ("summary", summary),
            ("diagnostics", diagnostics),
        )
    )


def format_integrity_text(report):
    status = "OK" if report["ok"] else "ISSUES"
    lines = [
        "integrity: %s (%d item(s), %d diagnostic(s))"
        % (status, report["item_count"], len(report["diagnostics"]))
    ]
    counts = report["summary"]["categories"]
    if counts:
        lines.append(
            "checks: "
            + ", ".join("%s=%d" % (key, counts[key]) for key in sorted(counts))
        )
    for row in report["diagnostics"]:
        if row["effective_severity"] == "info" and row["check_state"] == "skipped":
            continue
        location = _location(row)
        lines.append(
            "%s %s %s %s%s"
            % (
                row["effective_severity"].upper(),
                row["code"],
                row["category"],
                row["message"],
                " (%s)" % location if location else "",
            )
        )
        if row.get("hint"):
            lines.append("  Hint: %s" % row["hint"])
    return "\n".join(lines) + "\n"


def integrity_report_to_json(report):
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def _normalize_paths(paths, config):
    if paths is None or list(paths or []) == []:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=False)
        return ["life.txt"]
    return expand_paths(paths, stdin_when_empty=False)


def _attachment_rows(items, config, verify_files):
    if not any(item.details.get(key) for item in items for key in ATTACHMENT_KEYS):
        return []
    return attachment_diagnostics(items, config=config, verify=bool(verify_files))


def _ticket_rows(items, config, id_key):
    rows = []
    try:
        from .tickets import iter_tickets, validate_ticket
        from .ticket_activity import validate_ticket_history
    except Exception as exc:
        return [
            _row(
                severity="warning",
                code="I010",
                category="ticket",
                message="Ticket checks could not be loaded: %s." % exc,
                hint="Run ticket validation directly for details.",
                check_state="blocked",
            )
        ]
    for item in iter_tickets(items):
        rows.extend(validate_ticket(item, config, key=id_key))
    rows.extend(validate_ticket_history(items, config=config, key=id_key))
    return rows


def _workspace_rows(config):
    if not isinstance(config, dict) or not (
        config.get("workspaces") or config.get("default_workspace")
    ):
        return [
            _row(
                severity="info",
                code="I020",
                category="workspace",
                message="No named workspace context was configured.",
                hint="Use --config and --workspace to include workspace manifest checks.",
                check_state="skipped",
            )
        ]
    try:
        from .workspace import active_workspace_name, resolve_workspace
    except Exception as exc:
        return [
            _row(
                severity="warning",
                code="I021",
                category="workspace",
                message="Workspace checks could not be loaded: %s." % exc,
                hint="Run workspace validate directly for details.",
                check_state="blocked",
            )
        ]
    try:
        resolution = resolve_workspace(config, active_workspace_name(config))
    except ValueError as exc:
        return [
            _row(
                severity="error",
                code="I022",
                category="workspace",
                message=str(exc),
                hint="Fix the workspace configuration and retry.",
                check_state="blocked",
            )
        ]
    return [_dict_row(row, "workspace") for row in resolution.get("diagnostics", [])]


def _diagnostic_rows(diagnostics, line_ids):
    rows = []
    for diagnostic in diagnostics:
        if isinstance(diagnostic, dict):
            rows.append(_dict_row(diagnostic, None, line_ids))
        else:
            rows.append(_object_row(diagnostic, line_ids))
    return rows


def _object_row(diagnostic, line_ids):
    source = getattr(diagnostic, "source", None)
    line = getattr(diagnostic, "line", None)
    return _row(
        severity=getattr(diagnostic, "severity", "warning"),
        code=getattr(diagnostic, "code", "I999"),
        category=diagnostic_category(diagnostic),
        message=getattr(diagnostic, "message", ""),
        hint=getattr(diagnostic, "hint", ""),
        source_file=source,
        line=line,
        column=getattr(diagnostic, "column", None),
        item_id=line_ids.get((source, line)),
        check_state="reported",
    )


def _dict_row(row, category=None, line_ids=None):
    source = row.get("source")
    line = row.get("line")
    return _row(
        severity=row.get("severity", "warning"),
        code=row.get("code", "I999"),
        category=category or _category_for_code(row.get("code")),
        message=row.get("message", ""),
        hint=row.get("hint", ""),
        source_file=source,
        line=line,
        column=row.get("column"),
        item_id=(line_ids or {}).get((source, line)),
        check_state=row.get("check_state", "reported"),
    )


def _category_for_code(code):
    diagnostic = Diagnostic("warning", str(code or ""), "")
    if str(code or "").upper().startswith("F"):
        return "workspace"
    if str(code or "").upper().startswith("TK"):
        return "ticket"
    return diagnostic_category(diagnostic)


def _row(
    *,
    severity,
    code,
    category,
    message,
    hint="",
    source_file=None,
    line=None,
    column=None,
    item_id=None,
    check_state="reported",
):
    severity = str(severity or "warning").lower()
    return OrderedDict(
        (
            ("severity", severity),
            ("effective_severity", severity),
            ("code", str(code or "I999")),
            ("category", str(category or "semantic")),
            ("message", str(message or "")),
            ("hint", str(hint or "")),
            ("source_file", source_file),
            ("line", line),
            ("column", column),
            ("item_id", item_id),
            ("check_state", check_state),
        )
    )


def _summary(diagnostics):
    severities = OrderedDict()
    categories = OrderedDict()
    states = OrderedDict()
    for row in diagnostics:
        _increment(severities, row["effective_severity"])
        _increment(categories, row["category"])
        _increment(states, row["check_state"])
    return OrderedDict(
        (
            ("severities", severities),
            ("categories", categories),
            ("check_states", states),
        )
    )


def _increment(mapping, key):
    mapping[key] = mapping.get(key, 0) + 1


def _location(row):
    source = row.get("source_file")
    line = row.get("line")
    column = row.get("column")
    if source and line and column:
        return "%s:%s:%s" % (source, line, column)
    if source and line:
        return "%s:%s" % (source, line)
    if source:
        return str(source)
    return ""
