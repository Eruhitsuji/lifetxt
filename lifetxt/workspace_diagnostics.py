"""Workspace-level stable diagnostics for safety-sensitive configuration and links."""

from __future__ import unicode_literals

import json
import os
import re
from collections import OrderedDict

from .parser import parse_text
from .safety_foundation import (
    read_text_exact,
    serve_target_diagnostic,
    stable_diagnostics as _base_stable_diagnostics,
    validate_timezone,
)


DIRECTIVE_RE = re.compile(r"^#!\s*([^:]*)(?::(.*))?$")
LINK_KEYS = ("parent", "ref", "depends_on", "blocks", "related")


def diagnostic(severity, code, message, source=None, line=None, column=None, hint=""):
    return OrderedDict(
        (
            ("severity", severity),
            ("code", code),
            ("message", message),
            ("source", source),
            ("line", line),
            ("column", column),
            (
                "span",
                {
                    "start": {"line": line, "column": column},
                    "end": {"line": line, "column": column},
                },
            ),
            ("hint", hint),
        )
    )


def extended_file_diagnostics(path):
    text, _raw, _bom = read_text_exact(path)
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("#!"):
            match = DIRECTIVE_RE.match(line)
            key = (match.group(1) if match else "").strip()
            value = match.group(2) if match else None
            if not key or value is None or not value.strip():
                rows.append(
                    diagnostic(
                        "error",
                        "F111",
                        "Malformed metadata directive.",
                        path,
                        line_no,
                        1,
                        "Use #! key: value with a non-empty key and value.",
                    )
                )
            elif key.lower().replace("-", "_") == "timezone":
                valid, error = validate_timezone(value.strip())
                if not valid:
                    rows.append(
                        diagnostic(
                            "error",
                            "F114",
                            "Invalid timezone directive %r: %s" % (value.strip(), error),
                            path,
                            line_no,
                            1,
                            "Use an IANA timezone such as Asia/Tokyo or UTC.",
                        )
                    )
        prefix = line[: len(line) - len(line.lstrip(" \t"))]
        if "\t" in prefix:
            rows.append(
                diagnostic(
                    "warning",
                    "F112",
                    "Leading indentation contains a tab.",
                    path,
                    line_no,
                    1,
                    "Use spaces only; canonical hierarchy indentation is two spaces per level.",
                )
            )
        spaces = len(prefix.replace("\t", ""))
        if prefix and "\t" not in prefix and spaces % 2:
            rows.append(
                diagnostic(
                    "warning",
                    "F113",
                    "Indentation is not a multiple of two spaces.",
                    path,
                    line_no,
                    1,
                    "Use two spaces per hierarchy level.",
                )
            )
    return rows


def stable_file_diagnostics(path):
    report = _base_stable_diagnostics(path)
    rows = list(report.get("diagnostics") or []) + extended_file_diagnostics(path)
    rows = _sort_diagnostics(rows)
    return OrderedDict(
        (
            ("ok", not any(row.get("severity") == "error" for row in rows)),
            ("item_count", report.get("item_count", 0)),
            ("diagnostics", rows),
        )
    )


def workspace_diagnostics(
    paths,
    archive_paths=None,
    timer_paths=None,
    write_path=None,
    revision_metrics_path=None,
    journal_dir=None,
):
    active_paths = _normalized_existing(paths)
    archive_paths = _normalized_existing(archive_paths)
    all_paths = active_paths + [path for path in archive_paths if path not in active_paths]
    reports = OrderedDict()
    rows = []
    items = []
    for path in all_paths:
        report = stable_file_diagnostics(path)
        reports[path] = report
        rows.extend(report["diagnostics"])
        text, _raw, _bom = read_text_exact(path)
        parsed, _diagnostics = parse_text(text)
        for item in parsed:
            items.append((path, item))
    rows.extend(_workspace_id_and_link_diagnostics(items, set(archive_paths)))
    rows.extend(_timer_diagnostics(timer_paths or []))
    if write_path:
        target = serve_target_diagnostic(active_paths, write_path)
        if target.get("mismatch") or target.get("windows_drive_relative"):
            rows.append(
                diagnostic(
                    "error" if target.get("windows_drive_relative") else "warning",
                    "F120",
                    "; ".join(target.get("messages") or ["Unsafe write target configuration."]),
                    write_path,
                    1,
                    1,
                    "Use an absolute write target that is one of the active workspace inputs.",
                )
            )
    if revision_metrics_path:
        rows.extend(_revision_metrics_diagnostics(revision_metrics_path))
    if journal_dir:
        rows.extend(_transaction_diagnostics(journal_dir))
    rows = _deduplicate(_sort_diagnostics(rows))
    return OrderedDict(
        (
            ("ok", not any(row.get("severity") == "error" for row in rows)),
            ("paths", active_paths),
            ("archive_paths", archive_paths),
            ("file_reports", reports),
            ("item_count", len(items)),
            ("diagnostic_count", len(rows)),
            (
                "severity_counts",
                {
                    level: len([row for row in rows if row.get("severity") == level])
                    for level in ("error", "warning", "info")
                },
            ),
            ("diagnostics", rows),
        )
    )


def _workspace_id_and_link_diagnostics(items, archive_paths):
    rows = []
    by_id = OrderedDict()
    for path, item in items:
        for value in item.details.get("id", []):
            by_id.setdefault(str(value), []).append((path, item))
    for item_id, owners in by_id.items():
        if len(owners) > 1:
            locations = ["%s:%s" % (path, item.line or 1) for path, item in owners]
            rows.append(
                diagnostic(
                    "error",
                    "F115",
                    "Duplicate workspace ID %r at %s." % (item_id, ", ".join(locations)),
                    owners[0][0],
                    owners[0][1].line or 1,
                    1,
                    "IDs must be unique across active files and archives.",
                )
            )
    known = set(by_id)
    graph = OrderedDict((item_id, set()) for item_id in known)
    for path, item in items:
        owner_ids = [str(value) for value in item.details.get("id", [])]
        for key in LINK_KEYS:
            for target in item.details.get(key, []):
                target = str(target)
                if target not in known:
                    code = "F117" if key == "parent" else "F116"
                    message = (
                        "Missing parent ID %r." % target
                        if key == "parent"
                        else "Dangling %s reference to %r." % (key, target)
                    )
                    rows.append(
                        diagnostic(
                            "error" if key in ("parent", "depends_on") else "warning",
                            code,
                            message,
                            path,
                            item.line or 1,
                            1,
                            "Create the target ID or remove/update the reference.",
                        )
                    )
                if key == "depends_on":
                    for owner_id in owner_ids:
                        graph.setdefault(owner_id, set()).add(target)
                elif key == "blocks":
                    for owner_id in owner_ids:
                        graph.setdefault(target, set()).add(owner_id)
    for cycle in _dependency_cycles(graph):
        source_id = cycle[0]
        owner = by_id.get(source_id, [(None, None)])[0]
        rows.append(
            diagnostic(
                "error",
                "F118",
                "Dependency cycle detected: %s." % " -> ".join(cycle),
                owner[0],
                owner[1].line if owner[1] is not None else 1,
                1,
                "Remove at least one depends_on:/blocks: edge in the cycle.",
            )
        )
    return rows


def _dependency_cycles(graph):
    cycles = []
    visiting = []
    visited = set()

    def visit(node):
        if node in visiting:
            index = visiting.index(node)
            cycle = visiting[index:] + [node]
            normalized = _normalize_cycle(cycle)
            if normalized not in cycles:
                cycles.append(normalized)
            return
        if node in visited:
            return
        visiting.append(node)
        for child in sorted(graph.get(node, ())):
            if child in graph:
                visit(child)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return cycles


def _normalize_cycle(cycle):
    core = list(cycle[:-1])
    if not core:
        return cycle
    rotations = [core[index:] + core[:index] for index in range(len(core))]
    best = min(rotations)
    return best + [best[0]]


def _timer_diagnostics(paths):
    rows = []
    for path in paths:
        absolute = os.path.abspath(path)
        if not os.path.exists(absolute):
            continue
        try:
            with open(absolute, "r", encoding="utf-8") as handle:
                value = json.load(handle)
            if not isinstance(value, dict):
                raise ValueError("timer state root must be an object")
        except (OSError, ValueError) as exc:
            rows.append(
                diagnostic(
                    "error",
                    "F119",
                    "Corrupt timer state: %s" % exc,
                    absolute,
                    1,
                    1,
                    "Restore a valid JSON object from backup or use an explicit safe reset.",
                )
            )
    return rows


def _revision_metrics_diagnostics(path):
    absolute = os.path.abspath(path)
    if not os.path.exists(absolute):
        return []
    try:
        with open(absolute, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        total = int(value.get("legacy_fallback_total") or 0)
    except (OSError, ValueError, TypeError) as exc:
        return [
            diagnostic(
                "error",
                "F122",
                "Corrupt revision telemetry: %s" % exc,
                absolute,
                1,
                1,
                "Repair or reset telemetry with an expected revision.",
            )
        ]
    if total <= 0:
        return []
    return [
        diagnostic(
            "warning",
            "F121",
            "Legacy revision fallback has been used %d time(s)." % total,
            absolute,
            1,
            1,
            "Migrate clients to revision discovery and If-Match before enabling required mode.",
        )
    ]


def _transaction_diagnostics(journal_dir):
    from .transaction_journal import TERMINAL_STATES, inspect_journal, list_journals

    rows = []
    for summary in list_journals(journal_dir, include_terminal=True):
        path = summary.get("journal_path")
        state = summary.get("state")
        if state == "corrupt":
            rows.append(
                diagnostic(
                    "error",
                    "F123",
                    "Corrupt transaction journal: %s" % summary.get("error"),
                    path,
                    1,
                    1,
                    "Restore the journal directory from backup or export it before explicit abandonment.",
                )
            )
            continue
        if state in TERMINAL_STATES:
            continue
        try:
            report = inspect_journal(path)
        except Exception as exc:
            rows.append(
                diagnostic(
                    "error",
                    "F123",
                    "Cannot inspect transaction journal: %s" % exc,
                    path,
                    1,
                    1,
                    "Preserve the journal and use safety transactions inspect/export.",
                )
            )
            continue
        diverged = [row["path"] for row in report.get("observed_targets", []) if row.get("relation") == "diverged"]
        if diverged:
            rows.append(
                diagnostic(
                    "error",
                    "F126",
                    "Transaction recovery target diverged from both recorded revisions: %s."
                    % ", ".join(diverged),
                    path,
                    1,
                    1,
                    "Do not resume or compensate automatically; inspect and abandon only with a complete backup.",
                )
            )
        if state in ("compensating", "compensation_failed", "recovery_required"):
            rows.append(
                diagnostic(
                    "error",
                    "F125",
                    "Interrupted or failed transaction compensation in state %s." % state,
                    path,
                    1,
                    1,
                    "Run safety transactions inspect, then compensate or abandon with backup.",
                )
            )
        else:
            rows.append(
                diagnostic(
                    "error",
                    "F124",
                    "Interrupted transaction commit in state %s." % state,
                    path,
                    1,
                    1,
                    "Run safety transactions inspect, then resume or compensate explicitly.",
                )
            )
    return rows


def _normalized_existing(paths):
    result = []
    for path in paths or []:
        if not path or path == "-":
            continue
        absolute = os.path.abspath(path)
        if os.path.exists(absolute) and absolute not in result:
            result.append(absolute)
    return result


def _sort_diagnostics(rows):
    rank = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("source") or ""),
            int(row.get("line") or 0),
            int(row.get("column") or 0),
            rank.get(row.get("severity"), 9),
            str(row.get("code") or ""),
            str(row.get("message") or ""),
        ),
    )


def _deduplicate(rows):
    seen = set()
    result = []
    for row in rows:
        key = (
            row.get("source"),
            row.get("line"),
            row.get("column"),
            row.get("code"),
            row.get("message"),
        )
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
