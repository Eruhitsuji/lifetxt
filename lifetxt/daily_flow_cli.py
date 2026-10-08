"""Local read-only snapshot adapter and direct Daily Flow rendering (#1145)."""

import json
import os
import re
import stat
import sys
import unicodedata
from datetime import date

from .daily_flow import build_daily_flow
from .daily_flow_model import HARD_LIMITS
from .mutation import MutationError, read_text_snapshot
from .timezone_policy import now, resolve_timezone_name


def main(argv):
    """Reuse legacy parser/config/workspace helpers without timezone pre-reads."""
    from . import cli

    cleaned, config_path, workspace = cli._extract_config_arg(argv)
    args = cli.build_parser().parse_args(cleaned)
    args.config = config_path
    args.workspace = workspace
    args.config_data = cli.load_config(config_path)
    cli._maybe_apply_workspace(args)
    return command_flow(args)


def _safe(value):
    """Keep authored controls from injecting terminal lines or escape sequences."""
    return "".join(
        "\\u%04x" % ord(char) if unicodedata.category(char).startswith("C") else char
        for char in str(value)
    )


def _reference(item):
    if not item:
        return ""
    return "%s %s [id=%s source=%s line=%s]" % (
        item["kind"],
        _safe(item["title"]),
        _safe(item["id"] or "-"),
        item["source"],
        item["line"],
    )


def _reasons(rows):
    return "; ".join(
        row["code"]
        + (
            " " + _safe(json.dumps(row["params"], ensure_ascii=False, sort_keys=True))
            if row["params"]
            else ""
        )
        for row in rows
    )


def format_flow_text(result):
    """Render canonical rows in their existing order; never compute a plan."""
    completeness = result["completeness"]
    lines = [
        "Daily Flow Lite for %s (%s) — read-only suggestions, not saved"
        % (result["date"], result["timezone"]),
        "Evaluated at: %s" % result["evaluated_at"],
        "Completeness: %s; occupancy=%s; inventory=%s"
        % (completeness["state"], completeness["occupancy"], completeness["inventory"]),
    ]
    if result["window"]:
        window = result["window"]
        lines.append(
            "Window: %s..%s; effective start=%s"
            % (window["start"], window["end"], window["effective_start"])
        )
    if completeness["state"] != "complete":
        lines.append(
            "WARNING: plan is %s; do not treat unknown occupancy as free time."
            % completeness["state"]
        )
    lines.append("Timeline (%d):" % len(result["timeline"]))
    for row in result["timeline"]:
        lines.append(
            "  %s..%s [%s] %s"
            % (
                row["start"],
                row["end"],
                row["kind"],
                _reference(row.get("item") or row.get("candidate")),
            )
        )
        lines.append("    why: " + _reasons(row["why"]))
        if "deadline_status" in row:
            lines.append("    deadline: " + row["deadline_status"])
    lines.append("Instants (%d):" % len(result["instants"]))
    for row in result["instants"]:
        lines.append(
            "  %s [%s] %s" % (row["at"], row["source_field"], _reference(row["item"]))
        )
    lines.append("Certified residual free (%d):" % len(result["free"]))
    for row in result["free"]:
        lines.append("  %s..%s" % (row["start"], row["end"]))
    lines.append("Unplaced (%d):" % len(result["unplaced"]))
    for row in result["unplaced"]:
        lines.append(
            "  %s: %s%s"
            % (
                _reference(row["item"]),
                row["reason"],
                " (also: %s)" % ", ".join(row["secondary"]) if row["secondary"] else "",
            )
        )
        lines.append("    why: " + _reasons(row["why"]))
    lines.append("Diagnostics (%d):" % len(result["diagnostics"]))
    for row in result["diagnostics"]:
        lines.append(
            "  %s [%s/%s] %s %s"
            % (
                row["code"],
                row["severity"],
                row["effect"],
                _reference(row["item"]),
                _safe(json.dumps(row["params"], ensure_ascii=False, sort_keys=True)),
            )
        )
    lines.append("Excluded: " + json.dumps(result["excluded"], sort_keys=True))
    if result["source_revision"]:
        lines.append(
            "Source revisions: " + json.dumps(result["source_revision"], sort_keys=True)
        )
    return "\n".join(lines) + "\n"


def _validate_window(args):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        raise ValueError("flow --date must be YYYY-MM-DD.")
    try:
        selected = date.fromisoformat(args.date)
    except ValueError:
        raise ValueError("flow --date must be a valid calendar date.") from None
    if selected == date.max:
        raise ValueError("flow --date cannot be the maximum calendar date.")
    for flag, value in (("--day-start", args.day_start), ("--day-end", args.day_end)):
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("flow %s must be HH:MM (00:00..23:59)." % flag)
    if args.day_end != "00:00" and args.day_end <= args.day_start:
        raise ValueError(
            "flow --day-end must be later than --day-start (or 00:00 for next midnight)."
        )


def _paths(args, config):
    from .cli import _normalize_paths
    from .workspace import resolve_workspace, workspace_resolution_active

    if not args.paths and workspace_resolution_active(
        config, getattr(args, "workspace", None)
    ):
        resolution = resolve_workspace(config, getattr(args, "workspace", None) or None)
        if any(d["severity"] == "error" for d in resolution["diagnostics"]):
            raise ValueError(
                "flow workspace has errors; run lifetxt workspace doctor and fix its sources."
            )
        archives = set(resolution["archive_paths"])
        expanded = [p for p in resolution["input_paths"] if p not in archives]
        if not expanded or any(
            not s["exists"] for s in resolution["sources"] if s["role"] != "archive"
        ):
            raise ValueError(
                "flow workspace active sources are missing; fix the workspace before planning."
            )
    else:
        expanded = _normalize_paths(args.paths, config, stdin_when_empty=False) or [
            "life.txt"
        ]
    # Real-path identity admits aliases only once, including symlink aliases.
    result = list(
        dict.fromkeys(
            "-" if p == "-" else os.path.normcase(os.path.realpath(p)) for p in expanded
        )
    )
    if len(result) > HARD_LIMITS["context"]:
        raise ValueError(
            "flow has too many input sources; select a smaller active scope."
        )
    return result


def _read(path):
    # Bound before parsing. This is not a substitute for the core item limits.
    if not stat.S_ISREG(os.stat(path).st_mode):
        raise ValueError("flow inputs must be regular files (or explicit - for stdin).")
    if os.path.getsize(path) > HARD_LIMITS["text_chars"] * 4:
        raise ValueError(
            "flow source exceeds the 16 MB input bound; select a smaller active scope."
        )
    snapshot = read_text_snapshot(path)
    if snapshot.size > HARD_LIMITS["text_chars"] * 4:
        raise ValueError("flow source exceeds the 16 MB input bound.")
    return snapshot


def _parse(snapshots, stdin_text, config):
    from .cli import _set_source, _completed_parent_diagnostics
    from .ids import duplicate_id_diagnostics, id_key_from_config
    from .links import reference_diagnostics
    from .parser import parse_text

    key = id_key_from_config(config)
    items, diagnostics = [], []
    texts = [(path, snapshot.text) for path, snapshot in sorted(snapshots.items())]
    if stdin_text is not None:
        texts.append(("stdin", stdin_text))
    for source, text in texts:
        rows, notes = parse_text(
            text, id_key=key, check_ids=False, check_references=False
        )
        _set_source(rows, notes, source)
        items.extend(rows)
        diagnostics.extend(notes)
    diagnostics.extend(duplicate_id_diagnostics(items, key=key))
    diagnostics.extend(reference_diagnostics(items, key=key))
    diagnostics.extend(_completed_parent_diagnostics(items, key=key))
    if config.get("custom_fields"):
        from .custom_fields import generic_custom_field_diagnostics

        diagnostics = generic_custom_field_diagnostics(items, diagnostics, config)
    return items, diagnostics


def _unchanged(args, config, paths, snapshots):
    return set(_paths(args, config)) == set(paths) and all(
        _read(path).content_hash == snapshot.content_hash
        for path, snapshot in snapshots.items()
    )


def command_flow(args):
    """Read a complete selected local scope, retry one race, call shared core."""
    from .cli import _config, write_text

    _validate_window(args)
    config = _config(args)
    evaluated = now("UTC")  # one explicit reference, shared by bounded retries
    stdin_text = None
    result = None
    diagnostics = []
    try:
        for attempt in range(2):
            paths = _paths(args, config)
            if "-" in paths and stdin_text is None:
                stdin_text = sys.stdin.read(HARD_LIMITS["text_chars"] + 1)
                if len(stdin_text) > HARD_LIMITS["text_chars"]:
                    raise ValueError("flow stdin exceeds the input bound.")
            snapshots = {}
            text_chars = len(stdin_text or "") if "-" in paths else 0
            for path in paths:
                if path == "-":
                    continue
                snapshot = _read(path)
                text_chars += len(snapshot.text)
                if text_chars > HARD_LIMITS["text_chars"]:
                    raise ValueError(
                        "flow selected text exceeds the 4 million character input bound."
                    )
                snapshots[path] = snapshot
            first_text = stdin_text if paths[0] == "-" else snapshots[paths[0]].text
            zone = resolve_timezone_name(config, text=first_text or "")
            if zone.lower() in ("local", "host"):
                raise ValueError(
                    "flow requires a resolved timezone: add #! timezone: Asia/Tokyo (or UTC), or set defaults.timezone in config."
                )
            items, diagnostics = _parse(
                snapshots, stdin_text if "-" in paths else None, config
            )
            options = dict(
                date=args.date,
                day_start=args.day_start,
                day_end=args.day_end,
                timezone=zone,
                evaluated_at=evaluated,
                occupancy_complete=True,
                config=config,
                source_revisions={
                    path.replace("\\", "/"): s.content_hash
                    for path, s in snapshots.items()
                },
                input_diagnostics=diagnostics,
            )
            result = build_daily_flow(items, **options)
            if _unchanged(args, config, paths, snapshots):
                break
            if attempt == 1:
                result = build_daily_flow(
                    (), **{**options, "snapshot_consistent": False}
                )
    except (OSError, UnicodeError, MutationError) as exc:
        raise ValueError(
            "flow cannot read the complete active scope: %s. Check input files and retry."
            % _safe(exc)
        ) from None
    output = (
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.format == "json"
        else format_flow_text(result)
    )
    write_text(None, output)
    for diagnostic in diagnostics:
        sys.stderr.write(
            "%s: %s %s\n"
            % (diagnostic.severity.upper(), diagnostic.code, _safe(diagnostic.message))
        )
    if result["completeness"]["state"] != "complete":
        sys.stderr.write(
            "ERROR: flow is %s (%s); fix diagnostics or reload inputs and retry.\n"
            % (
                result["completeness"]["state"],
                ", ".join(result["completeness"]["reasons"]),
            )
        )
        return 1
    return 0
