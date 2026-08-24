"""CLI surfaces for the deterministic Personal Context toolkit."""

from __future__ import unicode_literals

import argparse
from collections import OrderedDict

from .extra_common import _json_text, _load_config, _load_items, _table, _write_output
from .personal_context import (
    DEFAULT_LIMIT,
    context_capsule,
    context_health,
    decision_memory,
    explain_personal_context_item,
    stage_memory_correction,
)
from .temporal_context import DEFAULT_STALE_DAYS
from .timezone_policy import resolve_timezone_name, timezone_context


def _add_common_read(parser, default_format="text"):
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--person", default="self")
    parser.add_argument("--stale-after-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--format", choices=("text", "json"), default=default_format)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("-o", "--output")
    parser.add_argument("--timezone")


def _build_parser():
    parser = argparse.ArgumentParser(prog="python -m lifetxt")
    subparsers = parser.add_subparsers(dest="command")

    context = subparsers.add_parser("context", help="Inspect/export Personal Context")
    context_sub = context.add_subparsers(dest="context_action")

    health = context_sub.add_parser("health", help="Inspect Personal Context health")
    _add_common_read(health)

    why = context_sub.add_parser("why", help="Explain one Personal Context item")
    why.add_argument("id")
    why.add_argument("paths", nargs="*")
    why.add_argument("--stale-after-days", type=int, default=DEFAULT_STALE_DAYS)
    why.add_argument("--format", choices=("text", "json"), default="text")
    why.add_argument("--pretty", action="store_true")
    why.add_argument("-o", "--output")
    why.add_argument("--timezone")

    capsule = context_sub.add_parser("capsule", help="Export bounded Personal Context")
    _add_common_read(capsule, default_format="json")
    capsule.add_argument("--tag", dest="tags", action="append", default=[])
    capsule.add_argument("--include-stale", action="store_true")
    capsule.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    memory = subparsers.add_parser("memory", help="Reviewable Personal Context mutation")
    memory_sub = memory.add_subparsers(dest="memory_action")
    correct = memory_sub.add_parser("correct", help="Stage a correction proposal")
    correct.add_argument("id")
    correct.add_argument("replacement")
    correct.add_argument("paths", nargs="*")
    correct.add_argument("--source", default="manual")
    correct.add_argument("--format", choices=("text", "json"), default="text")
    correct.add_argument("--pretty", action="store_true")
    correct.add_argument("-o", "--output")
    correct.add_argument("--timezone")

    decisions = subparsers.add_parser("decisions", help="List Personal Decision Memory")
    _add_common_read(decisions)
    decisions.add_argument("--project")
    decisions.add_argument("--include-stale", action="store_true")
    decisions.add_argument("--limit", type=int, default=DEFAULT_LIMIT)

    return parser


def _require_action(parser, args):
    if args.command == "context" and not args.context_action:
        parser.error("context requires health, why, or capsule")
    if args.command == "memory" and not args.memory_action:
        parser.error("memory requires correct")


def _health_text(report):
    counts = report["counts"]
    lines = [
        "Personal Context Health (person:%s)" % report["person"],
        "total=%d current=%d stale=%d superseded=%d missing_source=%d broken_reference=%d"
        % (
            counts["total"],
            counts["current"],
            counts["stale"],
            counts["superseded"],
            counts["missing_source"],
            counts["broken_reference"],
        ),
        "",
    ]
    rows = []
    for item in report["items"]:
        issues = []
        if item["missing_source"]:
            issues.append("missing-source")
        if item["broken_references"]:
            issues.append("broken-ref")
        rows.append(
            [
                item["state"],
                item.get("id") or "-",
                item["title"],
                ",".join(issues) or "-",
            ]
        )
    if rows:
        lines.append(_table(("STATE", "ID", "TITLE", "ISSUES"), rows).rstrip("\n"))
    else:
        lines.append("No Personal Context records found.")
    return "\n".join(lines) + "\n"


def _why_text(report):
    item = report["item"]
    lines = [
        "%s" % item["title"],
        "id: %s" % report["id"],
        "state: %s" % report["state"],
        "person: %s" % (", ".join(item["person"]) or "-"),
        "tags: %s" % (", ".join(item["tags"]) or "-"),
        "source: %s" % (", ".join(item["source"]) or "-"),
        "updated: %s" % (", ".join(item["updated"]) or "-"),
    ]
    for fact in report["temporal_facts"]:
        lines.append(
            "temporal: %s (%s=%s)"
            % (fact.get("rule"), fact.get("source_field"), fact.get("reference_time"))
        )
    for link in report["links"]:
        lines.append(
            "%s: %s %s %s [%s]"
            % (
                link.get("direction"),
                link.get("source_id") or link.get("source_location"),
                link.get("relation"),
                link.get("target_id"),
                link.get("status"),
            )
        )
    if report["corrected_by"]:
        lines.append(
            "corrected_by: %s"
            % ", ".join(
                "%s (%s)" % (entry.get("id") or "-", entry["title"])
                for entry in report["corrected_by"]
            )
        )
    return "\n".join(lines) + "\n"


def _capsule_text(report):
    lines = [
        "Personal Context Capsule",
        "revision: %s" % report["revision"],
        "person: %s" % report["person"],
        "count: %d" % report["count"],
        "",
    ]
    for item in report["items"]:
        lines.append(
            "- %s%s"
            % (
                ("[%s] " % item["id"]) if item.get("id") else "",
                item["title"],
            )
        )
    return "\n".join(lines) + "\n"


def _decisions_text(report):
    rows = []
    for item in report["items"]:
        rows.append(
            [
                item.get("id") or "-",
                ",".join(item.get("project") or []) or "-",
                item["title"],
            ]
        )
    if not rows:
        return "No decision memories found.\n"
    return _table(("ID", "PROJECT", "DECISION"), rows)


def _correction_text(report):
    return (
        "Staged Personal Context correction proposal %s for %s.\n"
        "Proposed record: %s\n"
        "Review with: lifetxt proposal show %s\n"
        "Accept with: lifetxt proposal accept %s\n"
        % (
            report["proposal_id"],
            report["target_id"],
            report["line"],
            report["proposal_id"],
            report["proposal_id"],
        )
    )


def _render(report, args, text_renderer):
    if args.format == "json":
        text = _json_text(report, pretty=args.pretty)
    else:
        text = text_renderer(report)
    _write_output(text, output=args.output)
    return 0


def _dispatch(args, config_data):
    if args.command == "context" and args.context_action == "health":
        items = _load_items(args.paths, config_data)
        report = context_health(
            items, person=args.person, stale_after_days=args.stale_after_days
        )
        return _render(report, args, _health_text)

    if args.command == "context" and args.context_action == "why":
        items = _load_items(args.paths, config_data)
        report = explain_personal_context_item(
            items, args.id, stale_after_days=args.stale_after_days
        )
        return _render(report, args, _why_text)

    if args.command == "context" and args.context_action == "capsule":
        items = _load_items(args.paths, config_data)
        report = context_capsule(
            items,
            person=args.person,
            tags=args.tags,
            include_stale=args.include_stale,
            limit=args.limit,
            stale_after_days=args.stale_after_days,
        )
        return _render(report, args, _capsule_text)

    if args.command == "memory" and args.memory_action == "correct":
        items = _load_items(args.paths, config_data, allow_stdin=False)
        report = stage_memory_correction(
            config_data,
            items,
            args.id,
            args.replacement,
            source=args.source,
        )
        return _render(report, args, _correction_text)

    if args.command == "decisions":
        items = _load_items(args.paths, config_data)
        report = decision_memory(
            items,
            person=args.person,
            project=args.project,
            include_stale=args.include_stale,
            limit=args.limit,
            stale_after_days=args.stale_after_days,
        )
        return _render(report, args, _decisions_text)

    raise ValueError("Unsupported Personal Context command.")


def main(argv=None, config_path=None, workspace_name=None):
    parser = _build_parser()
    args = parser.parse_args(list(argv or []))
    if not args.command:
        parser.error("a Personal Context command is required")
    _require_action(parser, args)
    config_data = _load_config(config_path, workspace_name=workspace_name)
    timezone_name = resolve_timezone_name(
        config_data, cli_timezone=getattr(args, "timezone", None)
    )
    with timezone_context(timezone_name):
        return _dispatch(args, config_data)
