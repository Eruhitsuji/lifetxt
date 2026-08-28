"""Read-only data integrity reporting for lifetxt."""

from __future__ import annotations

import json
import os
from collections import OrderedDict

from .attachments import ATTACHMENT_KEYS, attachment_diagnostics
from .config import config_paths
from .diagnostic_contract import diagnostic_category
from .ids import (
    collect_item_ids,
    duplicate_id_diagnostics,
    ensure_item_id,
    id_key_from_config,
    id_prefix_for_item,
)
from .links import LinksCycleError, critical_path, link_records, reference_diagnostics
from .model import Diagnostic, REFERENCE_KEYS
from .parser import parse_line, parse_text
from .paths import expand_paths
from .serializer import item_to_line


SCHEMA = "integrity-v1"
PLAN_SCHEMA = "integrity-plan-v1"
APPLY_SCHEMA = "integrity-apply-v1"
PROFILE_DEFAULT = "default"
PROFILE_STRICT = "strict"
PROFILES = (PROFILE_DEFAULT, PROFILE_STRICT)


AI_MEMORY_INTENT_TAGS = frozenset(["preference", "goal", "decision"])


def build_integrity_report(
    paths=None,
    config=None,
    verify_files=False,
    profile=None,
    ai_context=False,
    graph=False,
):
    """Build a read-only integrity report.

    This function intentionally performs no write, repair, migration, archive,
    cleanup, or recovery action. It only reads the selected sources and
    normalizes diagnostics produced by existing lifetxt validators.
    """

    config = config or {}
    profile = _normalize_profile(profile)
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
        diagnostics.extend(_missing_id_rows(items, id_key))
        cross_diagnostics.extend(duplicate_id_diagnostics(items, key=id_key))
        cross_diagnostics.extend(reference_diagnostics(items, key=id_key))
        cross_diagnostics.extend(_attachment_rows(items, config, verify_files))
        cross_diagnostics.extend(_ticket_rows(items, config, id_key))
        diagnostics.extend(_cross_file_registry_rows(items, id_key))
        diagnostics.extend(_source_uid_rows(items))
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
    diagnostics.extend(_recovery_rows(config))
    if ai_context:
        diagnostics.extend(_ai_context_rows(items, config))
    if graph:
        diagnostics.extend(_graph_rows(items, id_key))
    _apply_profile(diagnostics, profile)

    summary = _summary(diagnostics)
    return OrderedDict(
        (
            ("schema", SCHEMA),
            ("profile", profile),
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


def build_integrity_plan(
    paths=None,
    config=None,
    verify_files=False,
    profile=None,
    ai_context=False,
    graph=False,
):
    report = build_integrity_report(
        paths,
        config=config,
        verify_files=verify_files,
        profile=profile,
        ai_context=ai_context,
        graph=graph,
    )
    actions = []
    for row in report["diagnostics"]:
        action = _plan_action(row)
        if action is not None:
            actions.append(action)
    actions.sort(
        key=lambda row: (row["source_file"] or "", row["line"] or 0, row["code"])
    )
    return OrderedDict(
        (
            ("schema", PLAN_SCHEMA),
            ("report_schema", report["schema"]),
            ("profile", report["profile"]),
            ("ok", not any(row["classification"] == "blocked" for row in actions)),
            ("paths", report["paths"]),
            ("checked_paths", report["checked_paths"]),
            ("action_count", len(actions)),
            ("actions", actions),
        )
    )


def integrity_plan_to_json(plan):
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def apply_missing_id_repair(
    path,
    *,
    config=None,
    expected_revision=None,
    confirm=False,
    prefix=None,
):
    """Apply the narrow integrity repair for missing IDs.

    This is intentionally not a general repair engine. It mutates one explicit
    file only, requires operator confirmation, and relies on the shared
    mutation/CAS path for revision checking and serialized writes.
    """

    if not confirm:
        raise ValueError("integrity apply requires --confirm before writing.")
    if not expected_revision:
        raise ValueError("integrity apply requires --expected-revision before writing.")
    if not path:
        raise ValueError("integrity apply requires exactly one real file path.")
    config = config or {}
    normalized = _normalize_paths([path], config)
    if len(normalized) != 1 or normalized[0] == "-":
        raise ValueError("integrity apply requires exactly one real file path.")
    target = normalized[0]
    id_key = id_key_from_config(config)
    assignments = []

    def transform(text):
        items, diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        if _has_error(diagnostics):
            raise ValueError("Cannot apply missing-ID repair while parse errors exist.")
        existing = collect_item_ids(items, key=id_key)
        changed, new_text, records = _assign_missing_ids_in_text(
            target,
            text,
            id_key,
            existing,
            config,
            prefix=prefix,
        )
        assignments[:] = records
        return new_text if changed else text

    def validate(text):
        _items, diagnostics = parse_text(
            text,
            id_key=id_key,
            check_ids=False,
            check_references=False,
        )
        if _has_error(diagnostics):
            raise ValueError("Generated missing-ID repair did not parse cleanly.")

    from .mutation import mutate_text

    result = mutate_text(
        target,
        transform,
        expected_hash=expected_revision,
        operation="integrity_apply_assign_id",
        validate=validate,
        create=False,
    )
    return OrderedDict(
        (
            ("schema", APPLY_SCHEMA),
            ("operation", "assign_id"),
            ("path", target),
            ("before_revision", result.before_hash),
            ("after_revision", result.after_hash),
            ("changed", result.changed),
            ("assignment_count", len(assignments)),
            ("assignments", assignments),
        )
    )


def integrity_apply_to_json(result):
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def _normalize_paths(paths, config):
    if paths is None or list(paths or []) == []:
        configured = config_paths(config)
        if configured:
            return expand_paths(configured, stdin_when_empty=False)
        return ["life.txt"]
    return expand_paths(paths, stdin_when_empty=False)


def _normalize_profile(profile):
    value = str(profile or PROFILE_DEFAULT).strip().lower()
    if value not in PROFILES:
        raise ValueError(
            "Unknown integrity profile %r. Expected one of: %s."
            % (profile, ", ".join(PROFILES))
        )
    return value


def _apply_profile(diagnostics, profile):
    if profile == PROFILE_DEFAULT:
        return
    if profile == PROFILE_STRICT:
        for row in diagnostics:
            if row["severity"] == "warning":
                row["effective_severity"] = "error"


def _attachment_rows(items, config, verify_files):
    if not any(item.details.get(key) for item in items for key in ATTACHMENT_KEYS):
        return []
    return attachment_diagnostics(items, config=config, verify=bool(verify_files))


def _missing_id_rows(items, id_key):
    rows = []
    for item in items:
        if item.details.get(id_key):
            continue
        rows.append(
            _row(
                severity="warning",
                code="I210",
                category="id",
                message="Item is missing %s." % id_key,
                hint="Run `lifetxt integrity plan` to review a non-mutating ID assignment candidate.",
                source_file=getattr(item, "source", None),
                line=getattr(item, "line", None),
                check_state="reported",
                details=OrderedDict((("id_key", id_key),)),
            )
        )
    return rows


def _cross_file_registry_rows(items, id_key):
    rows = []
    index = OrderedDict()
    for item in items:
        for value in item.details.get(id_key, []):
            index.setdefault(str(value), []).append(item)
    for value, matches in index.items():
        sources = sorted(
            set(
                str(getattr(item, "source", ""))
                for item in matches
                if getattr(item, "source", None)
            )
        )
        if len(matches) > 1 and len(sources) > 1:
            first = matches[0]
            duplicate = matches[1]
            rows.append(
                _row(
                    severity="warning",
                    code="I220",
                    category="id",
                    message="Cross-file duplicate %s:%s appears in %d items."
                    % (id_key, value, len(matches)),
                    hint="Choose one authoritative record or assign a new ID before linking or syncing.",
                    source_file=getattr(duplicate, "source", None),
                    line=getattr(duplicate, "line", None),
                    item_id=value,
                    check_state="reported",
                    details=OrderedDict(
                        (
                            ("id_key", id_key),
                            ("id_value", value),
                            (
                                "first_location",
                                _item_location(first),
                            ),
                            ("sources", sources),
                        )
                    ),
                )
            )
    for item in items:
        source_id = _first_detail(item, id_key)
        for relation in REFERENCE_KEYS:
            for target_id in item.details.get(relation, []):
                target_id = str(target_id)
                matches = index.get(target_id, [])
                if not matches:
                    rows.append(
                        _row(
                            severity="warning",
                            code="I221",
                            category="reference",
                            message="Registry reference %s:%s has no target."
                            % (relation, target_id),
                            hint="Create the target item, fix the reference, or include the missing source file.",
                            source_file=getattr(item, "source", None),
                            line=getattr(item, "line", None),
                            item_id=source_id,
                            check_state="reported",
                            details=OrderedDict(
                                (
                                    ("relation", relation),
                                    ("target_id", target_id),
                                    ("target_state", "missing"),
                                )
                            ),
                        )
                    )
                elif len(matches) > 1:
                    rows.append(
                        _row(
                            severity="warning",
                            code="I222",
                            category="reference",
                            message="Registry reference %s:%s is ambiguous across %d targets."
                            % (relation, target_id, len(matches)),
                            hint="Resolve duplicate IDs before relying on this reference.",
                            source_file=getattr(item, "source", None),
                            line=getattr(item, "line", None),
                            item_id=source_id,
                            check_state="reported",
                            details=OrderedDict(
                                (
                                    ("relation", relation),
                                    ("target_id", target_id),
                                    ("target_state", "ambiguous"),
                                    (
                                        "target_locations",
                                        [_item_location(match) for match in matches],
                                    ),
                                )
                            ),
                        )
                    )
    return rows


def _source_uid_rows(items):
    pairs = OrderedDict()
    for item in items:
        source = _first_detail(item, "source")
        uid = _first_detail(item, "uid")
        if not source or not uid:
            continue
        pairs.setdefault((source, uid), []).append(item)
    rows = []
    for (source, uid), matches in pairs.items():
        if len(matches) > 1:
            rows.append(
                _row(
                    severity="warning",
                    code="I300",
                    category="sync",
                    message="Duplicate source/uid pair source:%s uid:%s appears in %d items."
                    % (source, uid, len(matches)),
                    hint="Keep one local representation for each external source UID.",
                    source_file=getattr(matches[1], "source", None),
                    line=getattr(matches[1], "line", None),
                    item_id=_first_detail(matches[1], "id"),
                    check_state="reported",
                    details=OrderedDict(
                        (
                            ("source", source),
                            ("uid", uid),
                            ("locations", [_item_location(item) for item in matches]),
                        )
                    ),
                )
            )
        generated = [item for item in matches if _is_generated_item(item)]
        manual = [item for item in matches if not _is_generated_item(item)]
        if generated and manual:
            rows.append(
                _row(
                    severity="warning",
                    code="I301",
                    category="sync",
                    message="Manual and generated records share source:%s uid:%s."
                    % (source, uid),
                    hint="Classify the authoritative record before the next import or sync.",
                    source_file=getattr(manual[0], "source", None),
                    line=getattr(manual[0], "line", None),
                    item_id=_first_detail(manual[0], "id"),
                    check_state="reported",
                    details=OrderedDict(
                        (
                            ("source", source),
                            ("uid", uid),
                            (
                                "generated_locations",
                                [_item_location(item) for item in generated],
                            ),
                            (
                                "manual_locations",
                                [_item_location(item) for item in manual],
                            ),
                        )
                    ),
                )
            )
    return rows


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


def _recovery_rows(config):
    try:
        from .transaction_journal import journal_directory, list_journals
        from .transaction_policy import verify_integrity_manifest
    except Exception as exc:
        return [
            _row(
                severity="warning",
                code="I400",
                category="recovery",
                message="Recovery checks could not be loaded: %s." % exc,
                hint="Run transaction recovery tools directly for details.",
                check_state="blocked",
            )
        ]
    journal_dir = journal_directory(config)
    if not os.path.isdir(journal_dir):
        return [
            _row(
                severity="info",
                code="I401",
                category="recovery",
                message="No transaction journal directory was found.",
                hint="Configure transactions.journal_dir to include recovery evidence checks.",
                source_file=journal_dir,
                check_state="skipped",
            )
        ]
    rows = []
    journals = list_journals(journal_dir, include_terminal=True)
    if not journals:
        rows.append(
            _row(
                severity="info",
                code="I402",
                category="recovery",
                message="Transaction journal directory contains no journal records.",
                source_file=journal_dir,
                check_state="passed",
            )
        )
    for journal in journals:
        path = journal.get("journal_path")
        severity = "warning" if journal.get("recovery_required") else "info"
        if journal.get("state") == "corrupt":
            severity = "error"
        rows.append(
            _row(
                severity=severity,
                code="I404" if journal.get("state") == "corrupt" else "I403",
                category="recovery",
                message="Transaction journal %s is in state %s."
                % (journal.get("transaction_id"), journal.get("state")),
                hint="Inspect transaction evidence before mutating affected files."
                if journal.get("recovery_required")
                else "",
                source_file=path,
                check_state="reported"
                if journal.get("recovery_required")
                else "passed",
                details=OrderedDict(journal),
            )
        )
        tx_dir = os.path.dirname(path) if path else None
        if not tx_dir:
            continue
        manifest_path = os.path.join(tx_dir, "integrity-manifest.json")
        if not os.path.exists(manifest_path):
            rows.append(
                _row(
                    severity="warning",
                    code="I405",
                    category="recovery",
                    message="Transaction evidence is missing integrity-manifest.json.",
                    hint="Export or archive recovery evidence to create a verifiable manifest.",
                    source_file=tx_dir,
                    check_state="reported",
                )
            )
            continue
        try:
            verification = verify_integrity_manifest(tx_dir)
        except Exception as exc:
            verification = {"ok": False, "error": str(exc)}
        rows.append(
            _row(
                severity="info" if verification.get("ok") else "error",
                code="I406" if verification.get("ok") else "I407",
                category="recovery",
                message="Transaction evidence manifest verification %s."
                % ("passed" if verification.get("ok") else "failed"),
                hint=""
                if verification.get("ok")
                else "Treat recovery evidence as unsupported until manifest errors are resolved.",
                source_file=manifest_path,
                check_state="passed" if verification.get("ok") else "blocked",
                details=OrderedDict(verification),
            )
        )
    return rows


def _ai_context_rows(items, config):
    rows = []
    rows.extend(_ai_workspace_rows(config))
    rows.extend(_personal_ai_memory_rows(items))
    return rows


def _ai_workspace_rows(config):
    if not isinstance(config, dict) or not (
        config.get("workspaces") or config.get("default_workspace")
    ):
        return [
            _row(
                severity="info",
                code="AI001",
                category="ai_context",
                message="No named workspace context was configured for AI-context checks.",
                hint="Use --config and --workspace to audit an AI-safe workspace shape.",
                check_state="skipped",
                details=OrderedDict((("area", "workspace"),)),
            )
        ]
    try:
        from .workspace import active_workspace_name, resolve_workspace
    except Exception as exc:
        return [
            _row(
                severity="warning",
                code="AI002",
                category="ai_context",
                message="AI workspace checks could not be loaded: %s." % exc,
                hint="Run workspace validation directly for details.",
                check_state="blocked",
                details=OrderedDict((("area", "workspace"),)),
            )
        ]
    try:
        resolution = resolve_workspace(config, active_workspace_name(config))
    except ValueError as exc:
        return [
            _row(
                severity="error",
                code="AI003",
                category="ai_context",
                message=str(exc),
                hint="Fix the workspace configuration before exposing it to an AI client.",
                check_state="blocked",
                details=OrderedDict((("area", "workspace"),)),
            )
        ]
    details = _ai_workspace_details(resolution)
    if not resolution.get("ok"):
        return [
            _row(
                severity="warning",
                code="AI100",
                category="ai_context",
                message="Workspace has diagnostics that weaken AI-context readiness.",
                hint="Resolve workspace diagnostics before using it as AI context.",
                source_file=resolution.get("write_file"),
                check_state="reported",
                details=details,
            )
        ]
    if not details["has_dedicated_write_target"]:
        return [
            _row(
                severity="warning",
                code="AI101",
                category="ai_context",
                message="AI workspace does not use a dedicated writable inbox target.",
                hint="Use broad read sources plus a separate writable source for AI proposals when possible.",
                source_file=resolution.get("write_file"),
                check_state="reported",
                details=details,
            )
        ]
    return [
        _row(
            severity="info",
            code="AI102",
            category="ai_context",
            message="AI workspace uses broad read context with a dedicated writable target.",
            hint="",
            source_file=resolution.get("write_file"),
            check_state="passed",
            details=details,
        )
    ]


def _ai_workspace_details(resolution):
    write_file = resolution.get("write_file")
    sources = resolution.get("sources") or []
    readable = []
    writable = []
    write_source = None
    for source in sources:
        resolved = source.get("resolved_path")
        if _path_key(resolved) == _path_key(write_file):
            write_source = source
        if source.get("default_visible") and resolved:
            readable.append(resolved)
        if source.get("writable") and resolved:
            writable.append(resolved)
    write_role = write_source.get("role") if write_source else None
    contextual_read_paths = [
        path for path in readable if _path_key(path) != _path_key(write_file)
    ]
    dedicated = bool(
        write_file
        and write_source
        and write_source.get("writable")
        and write_role not in ("readonly", "generated", "archive", "reference")
        and contextual_read_paths
        and _looks_like_ai_inbox_target(write_file)
    )
    return OrderedDict(
        (
            ("area", "workspace"),
            ("workspace", resolution.get("name")),
            ("write_file", write_file),
            ("write_role", write_role),
            ("readable_paths", readable),
            ("writable_paths", writable),
            ("has_broad_read_context", len(readable) > 1),
            ("looks_like_ai_inbox_target", _looks_like_ai_inbox_target(write_file)),
            ("has_dedicated_write_target", dedicated),
        )
    )


def _personal_ai_memory_rows(items):
    rows = []
    candidates = OrderedDict()
    for item in items:
        intent_tags = [
            value
            for value in (_detail_values(item, "tag"))
            if value.lower() in AI_MEMORY_INTENT_TAGS
        ]
        people = _detail_values(item, "person")
        if item.kind != "N" or not intent_tags or not people:
            continue
        item_id = _first_detail(item, "id")
        details = OrderedDict(
            (
                ("area", "personal_ai_memory"),
                ("person", people[0]),
                ("intent_tags", intent_tags),
                ("title_key", _normalized_title(item.title)),
            )
        )
        if item.status != "[N]":
            rows.append(
                _row(
                    severity="warning",
                    code="AI201",
                    category="ai_context",
                    message="Personal AI Memory candidate should use [N] status.",
                    hint="Change the status to [N] or use a task/event kind if it is actionable.",
                    source_file=getattr(item, "source", None),
                    line=getattr(item, "line", None),
                    item_id=item_id,
                    check_state="reported",
                    details=details,
                )
            )
        for intent in intent_tags:
            key = (people[0].lower(), intent.lower(), _normalized_title(item.title))
            candidates.setdefault(key, []).append(item)
    for (person, intent, title_key), matches in candidates.items():
        if len(matches) < 2:
            continue
        duplicate = matches[1]
        rows.append(
            _row(
                severity="warning",
                code="AI202",
                category="ai_context",
                message="Duplicate Personal AI Memory candidate for person:%s tag:%s."
                % (person, intent),
                hint="Review whether these memory records should be merged or differentiated.",
                source_file=getattr(duplicate, "source", None),
                line=getattr(duplicate, "line", None),
                item_id=_first_detail(duplicate, "id"),
                check_state="reported",
                details=OrderedDict(
                    (
                        ("area", "personal_ai_memory"),
                        ("person", person),
                        ("intent_tag", intent),
                        ("title_key", title_key),
                        ("locations", [_item_location(item) for item in matches]),
                    )
                ),
            )
        )
    return rows


#: Bounded top-N sizes for the graph health section's list-shaped details,
#: matching this module's existing bounded-report design; never an
#: unbounded dump of every id in a large workspace.
GRAPH_ORPHAN_LIMIT = 20
GRAPH_HUB_LIMIT = 10


def _graph_rows(items, id_key):
    """Read-only relation-graph health: orphans, hubs, components, longest chain.

    Reuses :func:`lifetxt.links.link_records` and
    :func:`lifetxt.links.critical_path` unmodified -- no relation-graph
    traversal is duplicated here, matching this module's existing
    reuse-existing-diagnostics design.
    """
    id_index = {}
    for item in items:
        for value in item.details.get(id_key, []) or []:
            id_index.setdefault(str(value), []).append(item)
    all_ids = set(id_index)
    if not all_ids:
        return [
            _row(
                severity="info",
                code="G001",
                category="graph",
                message="No items carry a unique id; graph health checks are skipped.",
                hint="Add id: details to items that should participate in the relation graph.",
                check_state="skipped",
                details=OrderedDict((("area", "graph"),)),
            )
        ]

    records = link_records(items, key=id_key)
    degree = {}
    adjacency = {}
    for rec in records:
        src = rec["source_id"] or rec["source_location"]
        tgt = rec["target_id"]
        if src in all_ids:
            degree[src] = degree.get(src, 0) + 1
        if tgt in all_ids:
            degree[tgt] = degree.get(tgt, 0) + 1
        if src in all_ids and tgt in all_ids:
            adjacency.setdefault(src, set()).add(tgt)
            adjacency.setdefault(tgt, set()).add(src)

    rows = [
        _orphan_row(all_ids, degree),
        _hub_row(degree),
        _component_row(all_ids, adjacency),
        _longest_chain_row(items, id_key),
    ]
    return rows


def _orphan_row(all_ids, degree):
    orphans = sorted(node_id for node_id in all_ids if degree.get(node_id, 0) == 0)
    if not orphans:
        return _row(
            severity="info",
            code="G002",
            category="graph",
            message="Every id-bearing item participates in at least one relation.",
            hint="",
            check_state="passed",
            details=OrderedDict((("count", 0),)),
        )
    return _row(
        severity="info",
        code="G002",
        category="graph",
        message="%d item(s) have a unique id but no relation of any kind."
        % len(orphans),
        hint="Add depends_on:/blocks:/parent:/ref:/related: if these items "
        "should connect to the graph.",
        check_state="reported",
        details=OrderedDict(
            (
                ("count", len(orphans)),
                ("ids", orphans[:GRAPH_ORPHAN_LIMIT]),
                ("truncated", len(orphans) > GRAPH_ORPHAN_LIMIT),
            )
        ),
    )


def _hub_row(degree):
    referenced = [(node_id, count) for node_id, count in degree.items() if count > 0]
    if not referenced:
        return _row(
            severity="info",
            code="G003",
            category="graph",
            message="No item participates in any relation.",
            hint="",
            check_state="skipped",
            details=OrderedDict((("hubs", []),)),
        )
    referenced.sort(key=lambda entry: (-entry[1], entry[0]))
    top = referenced[:GRAPH_HUB_LIMIT]
    return _row(
        severity="info",
        code="G003",
        category="graph",
        message="Top %d most-referenced item id(s) by relation count." % len(top),
        hint="",
        check_state="reported",
        details=OrderedDict(
            (
                (
                    "hubs",
                    [
                        OrderedDict((("id", node_id), ("references", count)))
                        for node_id, count in top
                    ],
                ),
            )
        ),
    )


def _component_row(all_ids, adjacency):
    visited = set()
    sizes = []
    for node_id in sorted(all_ids):
        if node_id in visited:
            continue
        stack = [node_id]
        visited.add(node_id)
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            for neighbor in adjacency.get(current, ()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    largest = max(sizes) if sizes else 0
    return _row(
        severity="info",
        code="G004",
        category="graph",
        message="%d connected component(s); largest has %d item(s)."
        % (len(sizes), largest),
        hint="",
        check_state="reported",
        details=OrderedDict(
            (("component_count", len(sizes)), ("largest_component_size", largest))
        ),
    )


def _longest_chain_row(items, id_key):
    try:
        chain = critical_path(items, key=id_key)
    except LinksCycleError as exc:
        return _row(
            severity="warning",
            code="G005",
            category="graph",
            message="Longest-chain check could not run: %s" % exc,
            hint="Resolve the dependency cycle (see check's W227) before "
            "computing a longest chain.",
            check_state="blocked",
            details=OrderedDict(),
        )
    return _row(
        severity="info",
        code="G005",
        category="graph",
        message="Longest depends_on/blocks chain has %d item(s)." % chain["length"],
        hint="",
        check_state="reported",
        details=OrderedDict((("length", chain["length"]), ("path", chain["path"]))),
    )


def _detail_values(item, key):
    return [str(value) for value in item.details.get(key, []) if str(value)]


def _normalized_title(value):
    return " ".join(str(value or "").lower().split())


def _path_key(path):
    if not path:
        return ""
    return os.path.normcase(os.path.abspath(path))


def _looks_like_ai_inbox_target(path):
    name = os.path.basename(str(path or "")).lower()
    return "inbox" in name or "proposal" in name


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
    details=None,
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
            ("details", details or OrderedDict()),
        )
    )


def _plan_action(row):
    source_file = row.get("source_file")
    code = row.get("code")
    if row.get("check_state") in ("passed", "skipped"):
        return None
    if row.get("effective_severity") == "info":
        return None
    classification = "manual"
    operation = "review"
    description = row.get("message", "")
    if code == "I210":
        classification = "automatic"
        operation = "assign_id"
        description = "Assign a generated ID to the item missing an ID."
    elif code in ("I001", "I404", "I407"):
        classification = "blocked"
    expected_revision = _current_revision(source_file)
    return OrderedDict(
        (
            ("classification", classification),
            ("operation", operation),
            ("code", code),
            ("category", row.get("category")),
            ("source_file", source_file),
            ("line", row.get("line")),
            ("item_id", row.get("item_id")),
            ("expected_revision", expected_revision),
            ("description", description),
            ("details", row.get("details") or OrderedDict()),
        )
    )


def _current_revision(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        from .write_operations import current_revision
    except Exception:
        return None
    try:
        return current_revision(path, allow_missing=False)
    except Exception:
        return None


def _first_detail(item, key):
    values = item.details.get(key) or []
    if not values:
        return ""
    return str(values[0])


def _is_generated_item(item):
    for key in ("generated", "managed", "imported"):
        for value in item.details.get(key, []):
            if str(value).lower() in ("1", "true", "yes", "y"):
                return True
    return False


def _assign_missing_ids_in_text(path, text, key, existing, config, prefix=None):
    raw_lines = text.splitlines(True)
    changed = False
    records = []
    new_lines = []
    for line_no, raw_line in enumerate(raw_lines, 1):
        body, ending = _split_line_ending(raw_line)
        item, diagnostics = parse_line(body, line_no)
        if item is None or _has_error(diagnostics) or item.details.get(key):
            new_lines.append(raw_line)
            continue
        assigned = ensure_item_id(
            item,
            existing_ids=existing,
            key=key,
            prefix=prefix or id_prefix_for_item(item, config),
        )
        new_line = item_to_line(item) + ending
        new_lines.append(new_line)
        changed = True
        records.append(
            OrderedDict(
                (
                    ("path", path),
                    ("line", line_no),
                    ("id", assigned),
                    ("type", item.kind),
                    ("status", item.status),
                    ("title", item.title),
                )
            )
        )
    if not raw_lines and text:
        new_lines.append(text)
    return changed, "".join(new_lines), records


def _split_line_ending(line):
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    if line.endswith("\r"):
        return line[:-1], "\r"
    return line, ""


def _has_error(diagnostics):
    return any(getattr(row, "severity", None) == "error" for row in diagnostics)


def _item_location(item):
    source = getattr(item, "source", None)
    line = getattr(item, "line", None)
    if source and line:
        return "%s:%s" % (source, line)
    if source:
        return str(source)
    if line:
        return "line %s" % line
    return ""


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
